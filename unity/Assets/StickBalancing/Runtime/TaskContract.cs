using System;

namespace StickBalancing
{
    // SI units; world x = rail, y = vertical, z = hinge axis. Zero = upright.
    [Serializable]
    public sealed class TaskContract
    {
        public int schema_version = 1;
        public int segments = 1;
        public float cart_mass = 2f;
        public float segment_mass = .5f;
        public float segment_length = 1f;
        public float force_limit = 100f;
        public float rail_half_length = 2.5f;
        public float physics_dt = .002f;
        public int decision_steps = 5;
        public float horizon_seconds = 30f;
        public float hold_seconds = 5f;
        public float angle_tolerance_deg = 10f;
        public float speed_tolerance = .5f;
        public int seed = 42;

        public void Validate()
        {
            if (schema_version != 1 || segments < 1 || segments > 3 || seed < 0 ||
                decision_steps < 1 || decision_steps > 100)
                throw new ArgumentException("Invalid schema, segment count, seed or decision period");
            foreach (float value in new[] { cart_mass, segment_mass, segment_length, force_limit,
                         rail_half_length, physics_dt, horizon_seconds, hold_seconds,
                         angle_tolerance_deg, speed_tolerance })
                if (!Finite(value) || value <= 0) throw new ArgumentException("Invalid physical parameter");
            if (hold_seconds >= horizon_seconds || angle_tolerance_deg >= 90)
                throw new ArgumentException("Invalid success window");
        }

        public static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
    }

    public enum EpisodeOutcome { Running, Success, RailExit, PhysicsError, TimeLimit }

    public sealed class SuccessMonitor
    {
        readonly TaskContract config;
        public double Held { get; private set; }
        public double Elapsed { get; private set; }
        public EpisodeOutcome Outcome { get; private set; }
        public SuccessMonitor(TaskContract config) { config.Validate(); this.config = config; }
        public void Reset() { Held = Elapsed = 0; Outcome = EpisodeOutcome.Running; }

        public EpisodeOutcome Step(float cart, float[] angles, float[] velocities)
        {
            if (Outcome != EpisodeOutcome.Running) throw new InvalidOperationException("Episode finished");
            if (angles.Length != config.segments || velocities.Length != config.segments)
                throw new ArgumentException("State dimension mismatch");
            if (!TaskContract.Finite(cart)) return Outcome = EpisodeOutcome.PhysicsError;
            double angle = 0, speed = 0;
            bool upright = true;
            for (int i = 0; i < angles.Length; i++)
            {
                if (!TaskContract.Finite(angles[i]) || !TaskContract.Finite(velocities[i]))
                    return Outcome = EpisodeOutcome.PhysicsError;
                angle += angles[i]; speed += velocities[i];
                double error = Math.Atan2(Math.Sin(angle), Math.Cos(angle));
                upright &= Math.Abs(error) < config.angle_tolerance_deg * Math.PI / 180 &&
                           Math.Abs(speed) < config.speed_tolerance;
            }
            Elapsed += config.physics_dt;
            if (Math.Abs(cart) >= config.rail_half_length) return Outcome = EpisodeOutcome.RailExit;
            Held = upright ? Held + config.physics_dt : 0;
            if (Held + 1e-6 >= config.hold_seconds) return Outcome = EpisodeOutcome.Success;
            if (Elapsed + 1e-6 >= config.horizon_seconds) return Outcome = EpisodeOutcome.TimeLimit;
            return Outcome;
        }
    }
}
