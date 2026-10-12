using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.UIElements;
using Debug = UnityEngine.Debug;

namespace StickBalancing
{
    // -----------------------------------------------------------------------
    // Machine à états de la session
    // -----------------------------------------------------------------------
    enum AppState { Ready, Starting, Training, Paused, Stopping, Evaluating, Testing, Error }

    // The UI never performs optimisation; it supervises one owned local process.
    public sealed class DesktopApp : MonoBehaviour
    {
        public PanelSettings panelSettings;

        [Serializable] class Item { public string id, label, path, status; public int steps, segments; }
        [Serializable] class Response { public bool ok; public string error, path, status; public int steps, successes, trials, segments; public Item[] items; }
        [Serializable] class Event { public string @event, message; public int steps; public float reward, elevation; public bool reward_available; public int successes, trials; }

        readonly ConcurrentQueue<Action> updates = new ConcurrentQueue<Action>();
        readonly List<Button> idleButtons = new List<Button>();
        readonly List<Button> projectButtons = new List<Button>();
        readonly Dictionary<string, Button> projectRows = new Dictionary<string, Button>();
        PendulumPreview preview;
        Label telemetry, projectTitle;
        VisualElement settings;
        bool showGrid = true;
        float zoom = 1;
        Process ownedProcess;
        string appRoot, dataRoot, selected;
        AppState appState = AppState.Ready;
        bool interactiveTest, quitAfterSave;
        long eventOffset;
        float nextPoll;

        // UI elements
        Label stateLabel, detail, counter, checkpointLabel, segmentsLabel;
        TextField nameInput;
        IntegerField seedInput, budgetInput;
        FloatField lengthInput, forceInput;
        DropdownField checkpointChoice, segmentsChoice;
        ScrollView experiments, history;
        Button pauseButton, resetButton;
        VisualElement rewardChart, successChart, stateIndicator, viewport;
        Label rewardRange, successRange;
        readonly List<float> rewards = new List<float>();
        readonly List<float> successRates = new List<float>();

        // -----------------------------------------------------------------------

        void Start()
        {
            appRoot = Application.isEditor
                ? Path.GetFullPath(Path.Combine(Application.dataPath, "../.."))
                : Path.GetDirectoryName(Application.dataPath);
            if (!File.Exists(Path.Combine(appRoot, "trainer/bootstrap.py")))
                appRoot = Path.GetFullPath(Path.Combine(appRoot, "../../.."));
            // Keep experiments created by the previous desktop title available after the rename.
            string legacyRoot = Path.Combine(
                Path.GetDirectoryName(Application.persistentDataPath),
                "StickBalancing RL", "experiments");
            dataRoot = Directory.Exists(legacyRoot)
                ? legacyRoot
                : Path.Combine(Application.persistentDataPath, "experiments");
            Directory.CreateDirectory(dataRoot);
            Application.runInBackground = true;
            Application.targetFrameRate = 60;
            preview = FindFirstObjectByType<PendulumPreview>();
            BuildInterface();
            SetState(AppState.Ready);
            RefreshExperiments();
            Application.wantsToQuit += CanQuit;
        }

        bool CanQuit()
        {
            if (ownedProcess == null) return true;
            quitAfterSave = true;
            StopOwned();
            detail.text = "Saving. Close after the operation finishes.";
            return false;
        }

        void OnDestroy() { Application.wantsToQuit -= CanQuit; }

        // -----------------------------------------------------------------------
        // State machine
        // -----------------------------------------------------------------------

        void SetState(AppState next)
        {
            appState = next;
            bool busy = next != AppState.Ready && next != AppState.Paused && next != AppState.Error;
            foreach (var btn in idleButtons) btn.SetEnabled(!busy);
            foreach (var btn in projectButtons) btn.SetEnabled(!busy && selected != null);
            settings?.SetEnabled(!busy);
            pauseButton.SetEnabled(next == AppState.Training || next == AppState.Evaluating || next == AppState.Testing);
            pauseButton.text = next == AppState.Testing || next == AppState.Evaluating
                ? "Stop the test"
                : "Pause and save";
            resetButton.SetEnabled(next == AppState.Testing && interactiveTest);

            stateLabel.text = next switch {
                AppState.Ready     => "Ready",
                AppState.Starting  => "Starting…",
                AppState.Training  => "Computing",
                AppState.Paused    => "Paused",
                AppState.Stopping  => "Saving…",
                AppState.Evaluating => "Measuring…",
                AppState.Testing   => "3D test running",
                AppState.Error     => "Error",
                _                  => "?"
            };

            Color indicatorColor = next switch {
                AppState.Training  => new Color(.14f, .34f, .84f),
                AppState.Paused    => new Color(.78f, .45f, .05f),
                AppState.Error     => new Color(.78f, .16f, .18f),
                AppState.Ready     => new Color(.08f, .52f, .34f),
                _                  => new Color(.38f, .43f, .51f)
            };
            stateIndicator.style.backgroundColor = indicatorColor;
        }

        // -----------------------------------------------------------------------
        // Process management
        // -----------------------------------------------------------------------

        static string Quote(string value) => "\"" + value.Replace("\"", "\\\"").TrimEnd('\\') + "\"";
        string Python => Path.Combine(appRoot, "trainer/runtime/python.exe");

        string WorkerPath(int segments)
        {
            string suffix = segments == 1 ? "" : $"N{segments}";
            string name = $"StickBalancingWorker{suffix}.exe";
            foreach (string dir in new[] { "workers", "builds/windows/worker" })
            {
                string p = Path.Combine(appRoot, dir, name);
                if (File.Exists(p)) return p;
            }
            return Path.Combine(appRoot, "builds/windows/worker", name);
        }

        void Run(string arguments, AppState runningState, Action<Response> success)
        {
            if (ownedProcess != null) return;
            if (!File.Exists(Python))
            {
                detail.text = "Private Python runtime missing. See the build instructions.";
                SetState(AppState.Error);
                return;
            }
            SetState(runningState);
            var output = new StringBuilder();
            var errors = new StringBuilder();
            var process = new Process {
                StartInfo = new ProcessStartInfo {
                    FileName = Python,
                    Arguments = "-I " + Quote(Path.Combine(appRoot, "trainer/bootstrap.py")) + " " + arguments,
                    UseShellExecute = false, CreateNoWindow = true, RedirectStandardInput = true,
                    RedirectStandardOutput = true, RedirectStandardError = true,
                    WorkingDirectory = appRoot,
                    StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
                }
            };
            process.OutputDataReceived += (_, e) => { if (e.Data != null) lock (output) output.AppendLine(e.Data); };
            process.ErrorDataReceived += (_, e) => { if (e.Data != null) lock (errors) { if (errors.Length < 8000) errors.AppendLine(e.Data); } };
            try
            {
                process.Start();
                ownedProcess = process;
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                System.Threading.Tasks.Task.Run(() => {
                    process.WaitForExit();
                    int code = process.ExitCode;
                    string result; lock (output) result = output.ToString();
                    updates.Enqueue(() => {
                        ownedProcess = null;
                        process.Dispose();
                        try {
                            var response = JsonUtility.FromJson<Response>(result);
                            if (code != 0)
                                throw new Exception(response != null && !string.IsNullOrEmpty(response.error)
                                    ? response.error : errors.ToString());
                            SetState(AppState.Ready);
                            success(response);
                        } catch (Exception ex) {
                            SetState(AppState.Error);
                            detail.text = ex.Message;
                        }
                        if (quitAfterSave) Application.Quit();
                    });
                });
            }
            catch (Exception ex)
            {
                ownedProcess = null;
                process.Dispose();
                SetState(AppState.Error);
                detail.text = ex.Message;
            }
        }

        void StopOwned()
        {
            if (ownedProcess == null) return;
            bool stopTest = appState == AppState.Testing || appState == AppState.Evaluating;
            SetState(AppState.Stopping);
            try {
                SendCommand(stopTest ? "stop" : "pause");
                pauseButton.SetEnabled(false);
            } catch (Exception ex) { detail.text = ex.Message; }
        }

        void SendCommand(string command)
        {
            if (ownedProcess == null) return;
            try {
                ownedProcess.StandardInput.WriteLine("{\"schema_version\":1,\"command\":\"" + command + "\"}");
                ownedProcess.StandardInput.Flush();
            } catch (Exception ex) { detail.text = ex.Message; }
        }

        // -----------------------------------------------------------------------
        // Commands
        // -----------------------------------------------------------------------

        void RefreshExperiments() => Run("desktop list --data-root " + Quote(dataRoot), AppState.Ready, response => {
            experiments.Clear();
            projectRows.Clear();
            if (response.items == null || response.items.Length == 0)
                experiments.Add(Text("No projects. Open “New project” below to get started.", 13));
            foreach (var item in response.items ?? Array.Empty<Item>())
            {
                var captured = item;
                var btn = new Button(() => Select(captured)) {
                    text = captured.label + $"  [N={captured.segments}]\n{captured.steps} steps"
                };
                StyleButton(btn);
                btn.AddToClassList("project-row");
                btn.tooltip = captured.label + " — " + captured.id;
                btn.EnableInClassList("selected", captured.path == selected);
                projectRows[captured.path] = btn;
                btn.style.height = 50;
                experiments.Add(btn);
            }
            SetState(AppState.Ready);
        });

        void Select(Item item)
        {
            if (appState != AppState.Ready && appState != AppState.Paused && appState != AppState.Error) return;
            selected = item.path;
            foreach (var entry in projectRows) entry.Value.EnableInClassList("selected", entry.Key == selected);
            projectTitle.text = item.label;
            try {
                var task = JsonUtility.FromJson<TaskContract>(File.ReadAllText(Path.Combine(selected, "task.json")));
                preview?.Configure(task);
            } catch (Exception ex) { detail.text = "Preview unavailable: " + ex.Message; }
            counter.text = item.steps + " steps";
            segmentsLabel.text = $"N = {item.segments} segment{(item.segments > 1 ? "s" : "")}";
            checkpointLabel.text = item.label + " • " + item.id.Substring(0, 8)
                + "\nOrigin: " + (item.steps == 0 ? "new" : "trained locally");
            detail.text = "Parameters preserved. Use the left panel to create a new experiment.";
            eventOffset = 0;
            rewards.Clear(); successRates.Clear();
            history.Clear();
            rewardRange.text = "No measurements available for this project";
            successRange.text = "No evaluation in this session";
            rewardChart.MarkDirtyRepaint(); successChart.MarkDirtyRepaint();
            SetState(AppState.Ready);
            PollEvents();
        }

        void CreateExperiment()
        {
            if (string.IsNullOrWhiteSpace(nameInput.value) || seedInput.value < 0 ||
                !TaskContract.Finite(lengthInput.value) || lengthInput.value <= 0 ||
                !TaskContract.Finite(forceInput.value) || forceInput.value <= 0) {
                detail.text = "Check the name, seed (≥ 0), length and force (> 0).";
                nameInput.Focus();
                return;
            }
            string num(float x) => x.ToString(CultureInfo.InvariantCulture);
            int segs = segmentsChoice.index + 1;
            Run("desktop create --data-root " + Quote(dataRoot)
                + " --label " + Quote(nameInput.value)
                + " --seed " + seedInput.value
                + " --length " + num(lengthInput.value)
                + " --force " + num(forceInput.value)
                + " --segments " + segs,
                AppState.Ready,
                response => {
                    Select(new Item {
                        id = Path.GetFileName(response.path),
                        label = nameInput.value,
                        path = response.path,
                        segments = segs,
                        steps = 0,
                        status = "ready"
                    });
                    RefreshExperiments();
                });
        }

        void StartTraining()
        {
            if (budgetInput.value < 256 || budgetInput.value > 10000000) { detail.text = "The budget must be between 256 and 10,000,000 steps."; budgetInput.Focus(); return; }
            if (string.IsNullOrEmpty(selected)) { detail.text = "Select an experiment."; return; }
            int segs = GetSelectedSegments();
            Run("desktop train --experiment " + Quote(selected)
                + " --player " + Quote(WorkerPath(segs))
                + " --steps " + budgetInput.value,
                AppState.Training,
                response => {
                    SetState(response.status == "paused" ? AppState.Paused : AppState.Ready);
                    counter.text = response.steps + " steps";
                    detail.text = response.status == "paused"
                        ? "Session paused. Checkpoint saved."
                        : "Session completed. Checkpoint saved.";
                });
        }

        void Evaluate(string checkpoint, bool visible)
        {
            if (string.IsNullOrEmpty(selected)) { detail.text = "Select an experiment."; return; }
            if (checkpoint != "zero" && !File.Exists(Path.Combine(selected, "snapshots", checkpoint + ".pt")))
            {
                detail.text = "This checkpoint does not exist yet. Run a first session.";
                return;
            }
            detail.text = "Frozen checkpoint: " + checkpoint + ". No optimization changes the parameters during these tests.";
            interactiveTest = visible;
            int segs = GetSelectedSegments();
            AppState runState = visible ? AppState.Testing : AppState.Evaluating;
            Run("evaluate --experiment " + Quote(selected)
                + " --player " + Quote(WorkerPath(segs))
                + " --checkpoint " + checkpoint
                + " --episodes " + (visible ? "1 --visible --interactive" : "20"),
                runState,
                response => {
                    SetState(AppState.Ready);
                    stateLabel.text = response.successes + " / " + response.trials + " successes";
                    detail.text = "Measurement completed. Parameters unchanged. Report saved in the experiment.";
                    // Record success rate for the chart.
                    if (response.trials > 0)
                    {
                        successRates.Add((float)response.successes / response.trials);
                        if (successRates.Count > 100) successRates.RemoveAt(0);
                        successChart.MarkDirtyRepaint();
                    }
                });
        }

        int GetSelectedSegments()
        {
            if (string.IsNullOrEmpty(selected)) return 1;
            try {
                var task = UnityEngine.JsonUtility.FromJson<TaskContract>(
                    File.ReadAllText(Path.Combine(selected, "task.json")));
                return Mathf.Clamp(task.segments, 1, 3);
            } catch { return 1; }
        }

        string SelectedCheckpoint => checkpointChoice.index switch {
            1 => "initial",
            2 => "best",
            _ => "latest"
        };

        // -----------------------------------------------------------------------
        // Event polling
        // -----------------------------------------------------------------------

        void Update()
        {
            while (updates.TryDequeue(out var update)) update();
            viewport?.MarkDirtyRepaint();
            if (preview?.Chain != null && telemetry != null) {
                var body = preview.Chain;
                telemetry.text = $"INDEPENDENT PREVIEW   |   x = {body.Cart.jointPosition[0]:F3} m   |   θ₁ = {Mathf.DeltaAngle(0, body.Links[0].jointPosition[0] * Mathf.Rad2Deg):F1}°   |   F = 0 N";
            }
            if (Time.unscaledTime >= nextPoll) { nextPoll = Time.unscaledTime + .5f; PollEvents(); }
        }

        void PollEvents()
        {
            if (string.IsNullOrEmpty(selected)) return;
            string path = Path.Combine(selected, "events.jsonl");
            if (!File.Exists(path)) return;
            try {
                using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                stream.Seek(eventOffset, SeekOrigin.Begin);
                using var reader = new StreamReader(stream, Encoding.UTF8);
                string remaining = reader.ReadToEnd();
                int complete = remaining.LastIndexOf('\n');
                if (complete < 0) return;
                string text = remaining.Substring(0, complete + 1);
                eventOffset += Encoding.UTF8.GetByteCount(text);
                foreach (string line in text.Split('\n'))
                {
                    if (string.IsNullOrWhiteSpace(line)) continue;
                    var entry = JsonUtility.FromJson<Event>(line);
                    if (entry == null) continue;
                    if (entry.@event == "metrics")
                    {
                        counter.text = entry.steps + " steps";
                        if (!entry.reward_available) continue;
                        rewards.Add(entry.reward);
                        if (rewards.Count > 300) rewards.RemoveAt(0);
                        rewardChart.MarkDirtyRepaint();
                        rewardRange.text = "Y : " + Mathf.Min(rewards.ToArray()).ToString("F3")
                            + " to " + Mathf.Max(rewards.ToArray()).ToString("F3")
                            + "   •   X: consecutive measurements, through step " + entry.steps;
                    }
                    if (entry.@event == "training" && appState == AppState.Starting)
                        SetState(AppState.Training);
                    if (entry.@event == "checkpoint")
                    {
                        history.Add(Text("Checkpoint • " + entry.steps + " steps", 12));
                        if (history.childCount > 20) history.RemoveAt(0);
                    }
                }
            } catch (IOException) { /* Writer may be replacing the file atomically. Retry next frame. */ }
        }

        // -----------------------------------------------------------------------
        // Interface construction
        // -----------------------------------------------------------------------

        void BuildInterface()
        {
            var document = gameObject.AddComponent<UIDocument>();
            var panel = panelSettings != null ? panelSettings : ScriptableObject.CreateInstance<PanelSettings>();
            panel.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            panel.referenceResolution = new Vector2Int(1440, 900);
            document.panelSettings = panel;
            var root = document.rootVisualElement;
            var theme = Resources.Load<StyleSheet>("ScientificWorkspace");
            if (theme != null) root.styleSheets.Add(theme);
            root.style.flexGrow = 1;
            // A focused scientific-workstation palette: a dark canvas keeps the
            // simulation legible while cyan is reserved for the active geometry.
            root.style.backgroundColor = new Color(.055f, .07f, .095f);
            root.style.color = new Color(.84f, .88f, .94f);
            root.style.fontSize = 15;
            root.style.unityFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            root.style.paddingTop = root.style.paddingBottom = 12;
            root.style.paddingLeft = root.style.paddingRight = 12;

            // Header
            var header = new VisualElement();
            header.style.flexDirection = FlexDirection.Row;
            header.style.alignItems = Align.Center;
            header.style.marginBottom = 16;
            root.Add(header);
            header.Add(Text("STICK BALANCING  /  LABORATORY", 18));
            var headerSpace = new VisualElement(); headerSpace.style.flexGrow = 1; header.Add(headerSpace);
            stateIndicator = new VisualElement();
            stateIndicator.style.width = stateIndicator.style.height = 16;
            stateIndicator.style.borderTopLeftRadius = stateIndicator.style.borderTopRightRadius =
                stateIndicator.style.borderBottomLeftRadius = stateIndicator.style.borderBottomRightRadius = 8;
            stateIndicator.style.marginLeft = 16;
            header.Add(stateIndicator);
            stateLabel = Text("SYSTEM READY", 15);
            stateLabel.style.marginLeft = 8;
            header.Add(stateLabel);
            var help = new Button(() => {
                detail.text = "1. Create or select a project. 2. Start computing. 3. Test a checkpoint in 3D or measure 20 trials. The central preview is an independent zero-force simulation. F1: help · F5: refresh.";
            }) { text = "Help  F1" };
            StyleButton(help); help.style.marginLeft = 16; header.Add(help);
            root.RegisterCallback<KeyDownEvent>(evt => {
                if (evt.keyCode == KeyCode.F1) { detail.text = help.tooltip = "Select → Compute → Test. The zero-force preview is independent of training. 3D tests open another window."; evt.StopPropagation(); }
                if (evt.keyCode == KeyCode.F5 && ownedProcess == null) { RefreshExperiments(); evt.StopPropagation(); }
            });

            var row = new VisualElement();
            row.style.flexDirection = FlexDirection.Row;
            row.style.flexGrow = 1;
            row.style.marginTop = 8;
            root.Add(row);

            // Left panel — experiments
            var left = Panel(265);
            row.Add(left);
            left.Add(Text("01  PROJECT EXPLORER", 14));
            experiments = new ScrollView();
            experiments.style.height = 180;
            experiments.style.flexGrow = 1;
            experiments.style.minHeight = 140;
            left.Add(experiments);
            AddButton(left, "Refresh the list", RefreshExperiments);
            left.Add(Separator());
            var creation = new Foldout { text = "New project", value = false };
            left.Add(creation);
            var form = new VisualElement();
            settings = form;
            creation.Add(form);
            nameInput = new TextField("Name") { value = "My pendulum" };
            form.Add(nameInput);
            seedInput = new IntegerField("Seed") { value = 42 };
            form.Add(seedInput);
            segmentsChoice = new DropdownField("Segments", new List<string> { "1 segment", "2 segments", "3 segments (exp.)" }, 0);
            form.Add(segmentsChoice);
            lengthInput = new FloatField("Length (m)") { value = 1 };
            form.Add(lengthInput);
            forceInput = new FloatField("Max. force (N)") { value = 100 };
            form.Add(forceInput);
            AddButton(form, "Create project", CreateExperiment);
            nameInput.tooltip = "Name shown in the explorer.";
            seedInput.tooltip = "Non-negative integer to reproduce initial conditions.";
            lengthInput.tooltip = "Length of each segment in metres; strictly positive.";
            forceInput.tooltip = "Maximum force applied to the cart, in newtons.";
            creation.tooltip = "Independent configurations. Initial position: pendulum down.";

            // Centre panel — preview + graphs
            var centre = new VisualElement();
            centre.style.flexGrow = 1;
            centre.style.marginLeft = centre.style.marginRight = 10;
            centre.style.minWidth = 300;
            row.Add(centre);
            centre.Add(Text("02  SIMULATION AREA", 14));
            projectTitle = Text("Select a project", 19);
            centre.Add(projectTitle);
            segmentsLabel = Text("N = 1 segment", 13);
            segmentsLabel.style.color = new Color(.12f, .82f, .94f);
            centre.Add(segmentsLabel);
            centre.Add(Text("Independent physics preview • zero force • 3D tests open another window", 12));
            var viewTools = new VisualElement(); viewTools.style.flexDirection = FlexDirection.Row; centre.Add(viewTools);
            void ViewTool(string caption, string hint, Action action) {
                var b = new Button(action) { text = caption, tooltip = hint }; StyleButton(b);
                b.style.flexGrow = 1; viewTools.Add(b);
            }
            ViewTool("Grid", "Show or hide the metric grid", () => showGrid = !showGrid);
            ViewTool("−", "Zoom out", () => zoom = Mathf.Max(.5f, zoom / 1.2f));
            ViewTool("+", "Zoom in", () => zoom = Mathf.Min(2.5f, zoom * 1.2f));
            ViewTool("Fit", "Restore the initial framing", () => zoom = 1);
            ViewTool("Reset", "Reset only the preview to its downward position", () => preview?.ResetPreview());
            viewport = new VisualElement();
            viewport.style.flexGrow = 1;
            viewport.style.minHeight = 220;
            viewport.style.marginTop = 8;
            viewport.style.marginBottom = 10;
            viewport.style.backgroundColor = new Color(.025f, .035f, .052f);
            viewport.style.overflow = Overflow.Hidden;
            viewport.style.borderTopWidth = viewport.style.borderBottomWidth =
                viewport.style.borderLeftWidth = viewport.style.borderRightWidth = 1;
            viewport.style.borderTopColor = viewport.style.borderBottomColor =
                viewport.style.borderLeftColor = viewport.style.borderRightColor = new Color(.18f, .27f, .35f);
            viewport.generateVisualContent += DrawViewport;
            centre.Add(viewport);
            telemetry = Text("Initializing the preview…", 11); centre.Add(telemetry);

            // Reward graph
            var rewardPanel = Panel(0);
            rewardPanel.style.height = 128;
            rewardPanel.style.paddingTop = rewardPanel.style.paddingBottom = 8;
            rewardPanel.style.marginBottom = 10;
            centre.Add(rewardPanel);
            rewardPanel.Add(Text("PROGRESS INDICATOR", 13));
            rewardRange = Text("No measured episodes", 11);
            rewardPanel.Add(rewardRange);
            rewardChart = new VisualElement();
            rewardChart.style.flexGrow = 1;
            rewardChart.style.minHeight = 28;
            rewardChart.generateVisualContent += DrawRewardChart;
            rewardPanel.Add(rewardChart);
            rewardPanel.Add(Text("Each point is an internal measurement. It is not a success rate.", 11));

            // Success rate graph
            var successPanel = Panel(0);
            successPanel.style.height = 128;
            successPanel.style.paddingTop = successPanel.style.paddingBottom = 8;
            centre.Add(successPanel);
            successPanel.Add(Text("SUCCESS RATE (frozen evaluations)", 13));
            successRange = Text("No evaluation started", 11);
            successPanel.Add(successRange);
            successChart = new VisualElement();
            successChart.style.flexGrow = 1;
            successChart.style.minHeight = 28;
            successChart.generateVisualContent += DrawSuccessChart;
            successPanel.Add(successChart);
            successPanel.Add(Text("Each point = 20 trials with frozen parameters.", 11));

            // Right panel — session controls
            var right = Panel(285);
            row.Add(right);
            right.Add(Text("03  SESSION CONTROL", 14));
            counter = Text("0 steps", 20);
            right.Add(counter);
            checkpointLabel = Text("No experiment selected", 13);
            right.Add(checkpointLabel);
            budgetInput = new IntegerField("Compute budget") { value = 2048 };
            right.Add(budgetInput);
            right.Add(Text("2,048: technical check. Increase the budget for a long session.", 11));
            AddButton(right, "Start / resume session", StartTraining);
            idleButtons[idleButtons.Count - 1].AddToClassList("primary");
            pauseButton = new Button(StopOwned) { text = "Pause and save" };
            StyleButton(pauseButton);
            right.Add(pauseButton);
            resetButton = new Button(() => SendCommand("reset")) { text = "Reset downward  •  test only" };
            StyleButton(resetButton);
            right.Add(resetButton);
            right.Add(Separator());
            checkpointChoice = new DropdownField("Checkpoint", new List<string> { "Latest", "Initial", "Best" }, 0);
            right.Add(checkpointChoice);
            AddButton(right, "Test the session  •  3D", () => Evaluate(SelectedCheckpoint, true));
            AddButton(right, "Measure  •  20 frozen trials", () => Evaluate(SelectedCheckpoint, false));
            AddButton(right, "Reference  •  zero action", () => Evaluate("zero", false));
            right.Add(Separator());
            detail = Text("Create an experiment or select one in the list.", 12);
            right.Add(detail);
            history = new ScrollView();
            history.style.flexGrow = 1;
            right.Add(history);

            // Footer
            var footer = Text(
                "TARGET  |  angle < 10°  •  speed < 0.5 rad/s  •  hold 5 s  •  horizon 30 s" +
                "     |     LOCAL COMPUTE  •  checkpoints: initial / latest / best", 11);
            footer.style.marginTop = 14;
            root.Add(footer);

            // Style all buttons
            root.Query<Button>().ForEach(StyleButton);
            foreach (var button in idleButtons) {
                if (button.parent == right) projectButtons.Add(button);
            }
            root.Query<VisualElement>(className: "unity-base-field__input").ForEach(input => {
                input.style.backgroundColor = new Color(.075f, .095f, .13f);
                input.style.color = new Color(.9f, .94f, .98f);
                input.style.borderTopColor = input.style.borderBottomColor =
                    input.style.borderLeftColor = input.style.borderRightColor = new Color(.25f, .36f, .46f);
            });
            root.Query<Label>(className: "unity-base-field__label").ForEach(label => {
                label.style.minWidth = 0;
                label.style.width = Length.Percent(100);
                label.style.color = new Color(.66f, .73f, .82f);
            });
            root.Query<VisualElement>().ForEach(element => {
                if (element.ClassListContains("unity-base-field")) {
                    element.style.flexDirection = FlexDirection.Column;
                    element.style.marginBottom = 7;
                }
            });

            // Initialize button states
            pauseButton.SetEnabled(false);
            resetButton.SetEnabled(false);
        }

        // -----------------------------------------------------------------------
        // UI helpers
        // -----------------------------------------------------------------------

        static Label Text(string text, int size)
        {
            var label = new Label(text);
            label.style.fontSize = size;
            label.style.whiteSpace = WhiteSpace.Normal;
            label.style.marginBottom = 6;
            return label;
        }

        static VisualElement Separator()
        {
            var sep = new VisualElement();
            sep.style.height = 1;
            sep.style.backgroundColor = new Color(.18f, .25f, .33f);
            sep.style.marginTop = sep.style.marginBottom = 8;
            return sep;
        }

        static VisualElement Panel(float width)
        {
            var panel = new VisualElement();
            if (width > 0) { panel.style.width = width; panel.style.flexShrink = 0; }
            panel.style.backgroundColor = new Color(.075f, .095f, .13f, .98f);
            panel.style.paddingTop = panel.style.paddingBottom =
                panel.style.paddingLeft = panel.style.paddingRight = 12;
            panel.style.borderTopLeftRadius = panel.style.borderTopRightRadius = 3;
            panel.style.borderBottomLeftRadius = panel.style.borderBottomRightRadius = 3;
            panel.style.borderTopWidth = panel.style.borderBottomWidth =
                panel.style.borderLeftWidth = panel.style.borderRightWidth = 1;
            panel.style.borderTopColor = panel.style.borderBottomColor =
            panel.style.borderLeftColor = panel.style.borderRightColor = new Color(.19f, .28f, .37f);
            return panel;
        }

        void AddButton(VisualElement parent, string text, Action callback)
        {
            var button = new Button(callback) { text = text };
            StyleButton(button);
            parent.Add(button);
            idleButtons.Add(button);
        }

        static void StyleButton(Button button)
        {
            button.style.height = 36;
            button.focusable = true;
            button.RegisterCallback<FocusInEvent>(_ => {
                button.style.borderTopColor = button.style.borderBottomColor =
                    button.style.borderLeftColor = button.style.borderRightColor = new Color(.45f, .82f, 1f);
            });
            button.RegisterCallback<FocusOutEvent>(_ => {
                button.style.borderTopColor = button.style.borderBottomColor =
                    button.style.borderLeftColor = button.style.borderRightColor = StyleKeyword.Null;
            });
            button.style.flexShrink = 0;
            button.style.marginBottom = 6;
            button.style.backgroundColor = StyleKeyword.Null;
            button.style.color = new Color(.9f, .97f, 1f);
            button.style.fontSize = 13;
            button.style.borderTopLeftRadius = button.style.borderTopRightRadius = 2;
            button.style.borderBottomLeftRadius = button.style.borderBottomRightRadius = 2;
            button.style.borderTopWidth = button.style.borderBottomWidth =
                button.style.borderLeftWidth = button.style.borderRightWidth = 1;
            button.style.borderTopColor = button.style.borderBottomColor =
            button.style.borderLeftColor = button.style.borderRightColor = StyleKeyword.Null;
        }

        // Project the actual independent physics preview into UI coordinates.
        void DrawViewport(MeshGenerationContext ctx)
        {
            float w = viewport.contentRect.width;
            float h = viewport.contentRect.height;
            if (w < 2 || h < 2) return;
            var p = ctx.painter2D;
            p.lineWidth = 1;
            p.strokeColor = new Color(.12f, .19f, .26f);
            if (preview?.Chain == null) return;
            var config = preview.Configuration;
            var chain = preview.Chain;
            float scale = Mathf.Min(w / (config.rail_half_length * 2 + 1), h / (config.segments * config.segment_length * 2 + 1)) * zoom;
            float railY = h * .5f;
            float pivotY = config.segments * config.segment_length + 1;
            Vector2 Project(Vector3 world) => new Vector2(w / 2 + world.x * scale, railY - (world.y - pivotY) * scale);
            float spacing = scale * .5f;
            if (showGrid && spacing > 1) {
                for (float x = w / 2 % spacing; x <= w; x += spacing) { p.BeginPath(); p.MoveTo(new Vector2(x, 0)); p.LineTo(new Vector2(x, h)); p.Stroke(); }
                for (float y = railY % spacing; y <= h; y += spacing) { p.BeginPath(); p.MoveTo(new Vector2(0, y)); p.LineTo(new Vector2(w, y)); p.Stroke(); }
            }
            p.strokeColor = new Color(.35f, .45f, .56f);
            p.lineWidth = 2;
            p.BeginPath(); p.MoveTo(new Vector2(w / 2 - config.rail_half_length * scale, railY)); p.LineTo(new Vector2(w / 2 + config.rail_half_length * scale, railY)); p.Stroke();

            var cart = Project(chain.Cart.transform.position);
            p.strokeColor = new Color(.96f, .55f, .18f);
            p.lineWidth = 3;
            p.BeginPath(); p.MoveTo(cart + new Vector2(-.2f * scale, -6)); p.LineTo(cart + new Vector2(.2f * scale, -6)); p.LineTo(cart + new Vector2(.2f * scale, 6)); p.LineTo(cart + new Vector2(-.2f * scale, 6)); p.ClosePath(); p.Stroke();

            p.strokeColor = new Color(.12f, .82f, .94f);
            p.lineWidth = 5;
            foreach (var link in chain.Links)
            {
                var joint = Project(link.transform.TransformPoint(new Vector3(0, -config.segment_length / 2, 0)));
                var end = Project(link.transform.TransformPoint(new Vector3(0, config.segment_length / 2, 0)));
                p.BeginPath(); p.MoveTo(joint); p.LineTo(end); p.Stroke();
            }

            p.strokeColor = new Color(.5f, .62f, .72f);
            p.lineWidth = 1;
            p.BeginPath(); p.MoveTo(new Vector2(22, 22)); p.LineTo(new Vector2(52, 22)); p.Stroke();
            p.BeginPath(); p.MoveTo(new Vector2(22, 22)); p.LineTo(new Vector2(22, 52)); p.Stroke();
        }

        // -----------------------------------------------------------------------
        // Charts
        // -----------------------------------------------------------------------

        void DrawRewardChart(MeshGenerationContext ctx)
        {
            DrawChartGrid(ctx, rewardChart);
            if (rewards.Count < 2) return;
            float min = Mathf.Min(rewards.ToArray()), max = Mathf.Max(rewards.ToArray());
            var p = ctx.painter2D;
            p.strokeColor = new Color(.25f, .8f, .94f);
            p.lineWidth = 2;
            p.BeginPath();
            for (int i = 0; i < rewards.Count; i++)
            {
                var pt = new Vector2(
                    i * rewardChart.contentRect.width / (rewards.Count - 1),
                    rewardChart.contentRect.height * (1 - (rewards[i] - min) / Mathf.Max(.001f, max - min)));
                if (i == 0) p.MoveTo(pt); else p.LineTo(pt);
            }
            p.Stroke();
        }

        static void DrawChartGrid(MeshGenerationContext ctx, VisualElement chart)
        {
            var p = ctx.painter2D;
            p.strokeColor = new Color(.20f, .27f, .34f); p.lineWidth = 1;
            for (int i = 1; i < 4; i++) {
                float y = chart.contentRect.height * i / 4;
                p.BeginPath(); p.MoveTo(new Vector2(0, y));
                p.LineTo(new Vector2(chart.contentRect.width, y)); p.Stroke();
            }
        }

        void DrawSuccessChart(MeshGenerationContext ctx)
        {
            DrawChartGrid(ctx, successChart);
            if (successRates.Count < 1) return;
            float w = successChart.contentRect.width;
            float h = successChart.contentRect.height;
            var p = ctx.painter2D;
            // Draw the 18/20 = 0.9 target line.
            p.strokeColor = new Color(.3f, .8f, .55f, .85f);
            p.lineWidth = 1;
            p.BeginPath();
            float targetY = h * (1f - 0.9f);
            p.MoveTo(new Vector2(0, targetY));
            p.LineTo(new Vector2(w, targetY));
            p.Stroke();
            // Draw the success rate curve.
            if (successRates.Count < 2) return;
            p.strokeColor = new Color(.25f, .8f, .94f);
            p.lineWidth = 2;
            p.BeginPath();
            for (int i = 0; i < successRates.Count; i++)
            {
                var pt = new Vector2(i * w / (successRates.Count - 1), h * (1f - successRates[i]));
                if (i == 0) p.MoveTo(pt); else p.LineTo(pt);
            }
            p.Stroke();
            successRange.text = "Rate: " + (successRates[successRates.Count - 1] * 100).ToString("F0")
                + " %   •   " + successRates.Count + " evaluation(s)   •   Green line = 90 % target";
        }
    }
}
