using System;
using System.IO;
using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;

namespace StickBalancing
{
    public sealed class SwingUpAgent : Agent
    {
        public TaskContract task = new TaskContract();
        CartChain chain;
        SuccessMonitor monitor;
        System.Random random;
        float action;
        float[] angles, speeds;
        bool ready;
        bool firstPhysicsStep;
        bool exactReset;
        string episodeLog;
        int episodeIndex;
        float maxCourse, controlEffort;
        public string LastOutcome { get; private set; } = "Ready";

        public override void Initialize()
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; i++)
            {
                if (args[i] == "--task-config") task = JsonUtility.FromJson<TaskContract>(File.ReadAllText(args[i + 1]));
                if (args[i] == "--episode-log") episodeLog = Path.GetFullPath(args[i + 1]);
            }
            exactReset = Array.IndexOf(args, "--exact-down") >= 0;
            task.Validate();
            // N=1 is validated; N=2 and N=3 are supported once physics validation passes.
            if (task.segments < 1 || task.segments > 3)
                throw new NotSupportedException("Only 1, 2 or 3 segments are supported");
            Time.fixedDeltaTime = task.physics_dt;
            Physics.gravity = new Vector3(0, -9.81f, 0);
            random = new System.Random(task.seed);
            chain = new CartChain(transform, task);
            monitor = new SuccessMonitor(task);
            angles = new float[task.segments]; speeds = new float[task.segments];
            // observation_size = 2 + 3 * segments (x, xdot, then sin/cos/omega per cumulated segment)
            var behavior = GetComponent<Unity.MLAgents.Policies.BehaviorParameters>();
            if (behavior != null)
                behavior.BrainParameters.VectorObservationSize = task.observation_size;
            GetComponent<DecisionRequester>().DecisionPeriod = task.decision_steps;
            GetComponent<DecisionRequester>().TakeActionsBetweenDecisions = true;
            MaxStep = 0; // Explicit simulated-time interruption below.
            ready = true;
        }

        public override void OnEpisodeBegin()
        {
            if (!ready) return;
            action = 0;
            chain.ResetDown(random, exactReset);
            monitor.Reset();
            firstPhysicsStep = true;
            maxCourse = controlEffort = 0;
        }

        public override void CollectObservations(VectorSensor sensor)
        {
            chain.Read(angles, speeds);
            sensor.AddObservation(chain.Cart.jointPosition[0] / task.rail_half_length);
            sensor.AddObservation(chain.Cart.jointVelocity[0] / 10f);
            float phi = 0, omega = 0;
            for (int i = 0; i < angles.Length; i++)
            {
                phi += angles[i]; omega += speeds[i];
                sensor.AddObservation(Mathf.Sin(phi)); sensor.AddObservation(Mathf.Cos(phi));
                sensor.AddObservation(omega / 10f);
            }
        }

        public override void OnActionReceived(ActionBuffers actions)
        {
            float value = actions.ContinuousActions[0];
            if (!TaskContract.Finite(value)) throw new InvalidOperationException("Nonfinite policy action");
            action = Mathf.Clamp(value, -1, 1);
        }

        public override void Heuristic(in ActionBuffers actionsOut)
        {
            // Zero-force reference if no trainer is connected; no hidden controller.
            var continuous = actionsOut.ContinuousActions;
            continuous[0] = 0;
        }

        void FixedUpdate()
        {
            if (!ready) return;
            if (firstPhysicsStep)
            {
                firstPhysicsStep = false;
                chain.Apply(action);
                return;
            }
            chain.Read(angles, speeds);
            float x = chain.Cart.jointPosition[0];
            var outcome = monitor.Step(x, angles, speeds);
            if (outcome == EpisodeOutcome.PhysicsError || !TaskContract.Finite(chain.Cart.jointVelocity[0]))
            {
                RecordEpisode(EpisodeOutcome.PhysicsError);
                ready = false;
                Application.Quit(2);
                throw new InvalidOperationException("Nonfinite articulation state; worker aborted");
            }
            maxCourse = Mathf.Max(maxCourse, Mathf.Abs(x));
            controlEffort += action * action * task.force_limit * task.force_limit * task.physics_dt;

            // Compute per-segment absolute orientation and total elevation.
            float phi = 0, omega = 0, elevation = 0;
            for (int i = 0; i < angles.Length; i++)
            {
                phi += angles[i];
                omega += speeds[i];
                // Elevation contribution: each segment's center-of-mass height (normalised to [0,1]).
                elevation += (1 + Mathf.Cos(phi)) / (2 * angles.Length);
                // Per-segment upright check logged as stats.
                float segError = Mathf.Atan2(Mathf.Sin(phi), Mathf.Cos(phi));
                Academy.Instance.StatsRecorder.Add($"Segment{i + 1}/ErrorDeg", segError * Mathf.Rad2Deg);
            }

            // Swing-up bonus: reward angular velocity toward upright when pendulum is below horizontal.
            float swingBonus = 0f;
            if (Mathf.Abs(phi) > Mathf.PI / 2 && omega * phi < 0) swingBonus = 1f;

            // Velocity bonus: reward cart movement when pendulum is down (encourages pumping).
            float velocityBonus = 0f;
            float cartVel = chain.Cart.jointVelocity[0];
            if (Mathf.Abs(phi) > Mathf.PI / 2 && Mathf.Abs(cartVel) > 0.5f) velocityBonus = 0.2f;

            // Stationary penalty: penalize high force with near-zero velocity (prevents "hold centre" hack).
            float stationaryPenalty = 0f;
            if (Mathf.Abs(cartVel) < 0.1f && Mathf.Abs(action) > 0.5f) stationaryPenalty = 0.5f * action * action;

            float effort = 0.00002f * action * action * task.force_limit * task.force_limit;
            float course = 0.0001f * x * x / (task.rail_half_length * task.rail_half_length);
            float holdBonus = monitor.Held > 0 ? 5f : 0f;
            AddReward((elevation * 5f + swingBonus + velocityBonus - effort - course - stationaryPenalty + holdBonus) * task.physics_dt);

            Academy.Instance.StatsRecorder.Add("Reward/Elevation", elevation);
            Academy.Instance.StatsRecorder.Add("Reward/SwingBonus", swingBonus);
            Academy.Instance.StatsRecorder.Add("Reward/VelocityBonus", velocityBonus);
            Academy.Instance.StatsRecorder.Add("Reward/StationaryPenalty", stationaryPenalty);
            Academy.Instance.StatsRecorder.Add("Reward/EffortPenalty", effort);
            Academy.Instance.StatsRecorder.Add("Reward/RailPenalty", course);

            if (outcome != EpisodeOutcome.Running)
            {
                LastOutcome = outcome.ToString();
                RecordEpisode(outcome);
                Academy.Instance.StatsRecorder.Add("Episode/" + LastOutcome, 1);
                Academy.Instance.StatsRecorder.Add("Episode/HoldSeconds", (float)monitor.Held);
                if (outcome == EpisodeOutcome.TimeLimit) EpisodeInterrupted();
                else EndEpisode();
                return;
            }
            chain.Apply(action); // Same force held across the fixed physics substeps.
        }

        [Serializable]
        sealed class EpisodeRecord
        {
            public int schema_version = 1;
            public int episode, seed, segments;
            public string outcome;
            public double elapsed_seconds, held_seconds;
            public float max_cart_m, effort_n2_s;
        }

        void RecordEpisode(EpisodeOutcome outcome)
        {
            if (string.IsNullOrEmpty(episodeLog)) return;
            Directory.CreateDirectory(Path.GetDirectoryName(episodeLog));
            var record = new EpisodeRecord {
                episode = episodeIndex++, seed = task.seed, segments = task.segments,
                outcome = outcome.ToString(),
                elapsed_seconds = monitor.Elapsed, held_seconds = monitor.Held,
                max_cart_m = maxCourse, effort_n2_s = controlEffort
            };
            File.AppendAllText(episodeLog, JsonUtility.ToJson(record) + "\n");
        }
    }
}
