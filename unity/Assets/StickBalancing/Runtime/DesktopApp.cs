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
        VisualElement rewardChart, successChart, stateIndicator;
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
            dataRoot = Path.Combine(Application.persistentDataPath, "experiments");
            Directory.CreateDirectory(dataRoot);
            Application.runInBackground = true;
            Application.targetFrameRate = 60;
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
            detail.text = "Sauvegarde en cours. Fermez après la fin de l'opération.";
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
            pauseButton.SetEnabled(next == AppState.Training || next == AppState.Evaluating || next == AppState.Testing);
            pauseButton.text = next == AppState.Testing || next == AppState.Evaluating
                ? "Arrêter le test"
                : "Pause et sauvegarde";
            resetButton.SetEnabled(next == AppState.Testing && interactiveTest);

            stateLabel.text = next switch {
                AppState.Ready     => "Prêt",
                AppState.Starting  => "Démarrage…",
                AppState.Training  => "Entraînement",
                AppState.Paused    => "En pause",
                AppState.Stopping  => "Sauvegarde…",
                AppState.Evaluating => "Évaluation…",
                AppState.Testing   => "Test en cours",
                AppState.Error     => "Erreur",
                _                  => "?"
            };

            Color indicatorColor = next switch {
                AppState.Training  => new Color(.1f, .75f, .85f),
                AppState.Paused    => new Color(.9f, .6f, .1f),
                AppState.Error     => new Color(.9f, .3f, .1f),
                AppState.Ready     => new Color(.2f, .75f, .2f),
                _                  => new Color(.55f, .55f, .55f)
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
                detail.text = "Runtime Python privé absent. Consultez les instructions de construction.";
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
            SetState(AppState.Stopping);
            try {
                SendCommand(appState == AppState.Testing || appState == AppState.Evaluating ? "stop" : "pause");
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
            foreach (var item in response.items ?? Array.Empty<Item>())
            {
                var captured = item;
                var btn = new Button(() => Select(captured)) {
                    text = captured.label + $"  [N={captured.segments}]\n{captured.steps} étapes"
                };
                StyleButton(btn);
                btn.style.height = 50;
                experiments.Add(btn);
            }
            SetState(AppState.Ready);
        });

        void Select(Item item)
        {
            if (appState != AppState.Ready && appState != AppState.Paused && appState != AppState.Error) return;
            selected = item.path;
            counter.text = item.steps + " étapes";
            segmentsLabel.text = $"N = {item.segments} segment{(item.segments > 1 ? "s" : "")}";
            checkpointLabel.text = item.label + " • " + item.id.Substring(0, 8)
                + "\nOrigine : " + (item.steps == 0 ? "neuf" : "entraîné localement");
            detail.text = "Paramètres conservés. Les champs gauches servent à créer un nouvel agent.";
            eventOffset = 0;
            rewards.Clear(); successRates.Clear();
            history.Clear();
            PollEvents();
        }

        void CreateExperiment()
        {
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
            if (string.IsNullOrEmpty(selected)) { detail.text = "Sélectionnez une expérience."; return; }
            int segs = GetSelectedSegments();
            Run("desktop train --experiment " + Quote(selected)
                + " --player " + Quote(WorkerPath(segs))
                + " --steps " + budgetInput.value,
                AppState.Training,
                response => {
                    SetState(response.status == "paused" ? AppState.Paused : AppState.Ready);
                    counter.text = response.steps + " étapes";
                    detail.text = response.status == "paused"
                        ? "Session en pause. Checkpoint sauvegardé."
                        : "Session terminée. Checkpoint sauvegardé.";
                });
        }

        void Evaluate(string checkpoint, bool visible)
        {
            if (string.IsNullOrEmpty(selected)) { detail.text = "Sélectionnez une expérience."; return; }
            if (checkpoint != "zero" && !File.Exists(Path.Combine(selected, "snapshots", checkpoint + ".pt")))
            {
                detail.text = "Ce checkpoint n'existe pas encore. Lancez une première session.";
                return;
            }
            detail.text = "Modèle figé : " + checkpoint + ". Aucune optimisation pendant ces essais.";
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
                    stateLabel.text = response.successes + " / " + response.trials + " réussites";
                    detail.text = "Évaluation terminée. Poids inchangés. Rapport enregistré dans l'expérience.";
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
                var meta = UnityEngine.JsonUtility.FromJson<Item>(
                    File.ReadAllText(Path.Combine(selected, "experiment.json")));
                return Mathf.Clamp(meta.segments, 1, 3);
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
                        counter.text = entry.steps + " étapes";
                        if (!entry.reward_available) continue;
                        rewards.Add(entry.reward);
                        if (rewards.Count > 300) rewards.RemoveAt(0);
                        rewardChart.MarkDirtyRepaint();
                        rewardRange.text = "Y : " + Mathf.Min(rewards.ToArray()).ToString("F3")
                            + " à " + Mathf.Max(rewards.ToArray()).ToString("F3")
                            + "   •   X : relevés successifs, jusqu'au pas " + entry.steps;
                    }
                    if (entry.@event == "training" && appState == AppState.Starting)
                        SetState(AppState.Training);
                    if (entry.@event == "checkpoint")
                    {
                        history.Add(Text("Checkpoint • " + entry.steps + " étapes", 12));
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
            root.style.flexGrow = 1;
            root.style.color = new Color(.88f, .93f, .97f);
            root.style.fontSize = 15;
            root.style.unityFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            root.style.paddingTop = root.style.paddingBottom = 24;
            root.style.paddingLeft = root.style.paddingRight = 28;

            // Header
            var header = new VisualElement();
            header.style.flexDirection = FlexDirection.Row;
            header.style.alignItems = Align.Center;
            header.style.marginBottom = 16;
            root.Add(header);
            header.Add(Text("STICK / BALANCING", 28));
            stateIndicator = new VisualElement();
            stateIndicator.style.width = stateIndicator.style.height = 16;
            stateIndicator.style.borderTopLeftRadius = stateIndicator.style.borderTopRightRadius =
                stateIndicator.style.borderBottomLeftRadius = stateIndicator.style.borderBottomRightRadius = 8;
            stateIndicator.style.marginLeft = 16;
            header.Add(stateIndicator);
            stateLabel = Text("Prêt", 20);
            stateLabel.style.marginLeft = 8;
            header.Add(stateLabel);

            var row = new VisualElement();
            row.style.flexDirection = FlexDirection.Row;
            row.style.flexGrow = 1;
            row.style.marginTop = 8;
            root.Add(row);

            // Left panel — experiments
            var left = Panel(300);
            row.Add(left);
            left.Add(Text("01   EXPÉRIENCES", 17));
            experiments = new ScrollView();
            experiments.style.height = 180;
            left.Add(experiments);
            AddButton(left, "Actualiser la liste", RefreshExperiments);
            left.Add(Separator());
            left.Add(Text("Créer un agent neuf", 17));
            nameInput = new TextField("Nom") { value = "Mon pendule" };
            left.Add(nameInput);
            seedInput = new IntegerField("Graine") { value = 42 };
            left.Add(seedInput);
            segmentsChoice = new DropdownField("Segments", new List<string> { "1 segment", "2 segments", "3 segments (exp.)" }, 0);
            left.Add(segmentsChoice);
            lengthInput = new FloatField("Longueur (m)") { value = 1 };
            left.Add(lengthInput);
            forceInput = new FloatField("Force max. (N)") { value = 100 };
            left.Add(forceInput);
            AddButton(left, "＋ Nouvelle expérience", CreateExperiment);
            left.Add(Text("Chaque expérience est indépendante. Le pendule démarre en bas.", 12));

            // Centre panel — preview + graphs
            var centre = new VisualElement();
            centre.style.flexGrow = 1;
            centre.style.marginLeft = centre.style.marginRight = 18;
            row.Add(centre);
            centre.Add(Text("LABORATOIRE D'APPRENTISSAGE PAR RENFORCEMENT", 17));
            segmentsLabel = Text("N = 1 segment", 13);
            segmentsLabel.style.color = new Color(.5f, .8f, .9f);
            centre.Add(segmentsLabel);
            centre.Add(Text("Aperçu physique • commande nulle  —  Les essais d'un checkpoint ouvrent une fenêtre 3D séparée.", 13));
            var spacer = new VisualElement();
            spacer.style.flexGrow = 1;
            centre.Add(spacer);

            // Reward graph
            var rewardPanel = Panel(0);
            rewardPanel.style.height = 145;
            rewardPanel.style.marginBottom = 10;
            centre.Add(rewardPanel);
            rewardPanel.Add(Text("RÉCOMPENSE D'ENTRAÎNEMENT", 13));
            rewardRange = Text("Aucun épisode mesuré", 11);
            rewardPanel.Add(rewardRange);
            rewardChart = new VisualElement();
            rewardChart.style.flexGrow = 1;
            rewardChart.generateVisualContent += DrawRewardChart;
            rewardPanel.Add(rewardChart);
            rewardPanel.Add(Text("Chaque point provient du trainer. La récompense n'est pas un taux de réussite.", 11));

            // Success rate graph
            var successPanel = Panel(0);
            successPanel.style.height = 145;
            centre.Add(successPanel);
            successPanel.Add(Text("TAUX DE RÉUSSITE (évaluations figées)", 13));
            successRange = Text("Aucune évaluation lancée", 11);
            successPanel.Add(successRange);
            successChart = new VisualElement();
            successChart.style.flexGrow = 1;
            successChart.generateVisualContent += DrawSuccessChart;
            successPanel.Add(successChart);
            successPanel.Add(Text("Chaque point = une évaluation 20 essais, modèle figé, sans apprentissage.", 11));

            // Right panel — agent + commands
            var right = Panel(300);
            row.Add(right);
            right.Add(Text("02   AGENT LOCAL", 17));
            counter = Text("0 étapes", 20);
            right.Add(counter);
            checkpointLabel = Text("Aucune expérience sélectionnée", 13);
            right.Add(checkpointLabel);
            budgetInput = new IntegerField("Décisions") { value = 2048 };
            right.Add(budgetInput);
            right.Add(Text("2 048 : contrôle technique. Augmenter pour une vraie campagne.", 11));
            AddButton(right, "▶  Démarrer / reprendre", StartTraining);
            pauseButton = new Button(StopOwned) { text = "Pause et sauvegarde" };
            StyleButton(pauseButton);
            right.Add(pauseButton);
            resetButton = new Button(() => SendCommand("reset")) { text = "Remettre en bas  •  test seulement" };
            StyleButton(resetButton);
            right.Add(resetButton);
            right.Add(Separator());
            checkpointChoice = new DropdownField("Checkpoint", new List<string> { "Dernier", "Initial", "Meilleur" }, 0);
            right.Add(checkpointChoice);
            AddButton(right, "Tester le modèle  •  3D", () => Evaluate(SelectedCheckpoint, true));
            AddButton(right, "Évaluer  •  20 essais figés", () => Evaluate(SelectedCheckpoint, false));
            AddButton(right, "Référence  •  commande nulle", () => Evaluate("zero", false));
            right.Add(Separator());
            detail = Text("Créez une expérience ou sélectionnez-en une dans la liste.", 12);
            right.Add(detail);
            history = new ScrollView();
            history.style.flexGrow = 1;
            right.Add(history);

            // Footer
            var footer = Text(
                "OBJECTIF   < 10°  •  < 0,5 rad/s  •  maintien 5 s  •  horizon 30 s" +
                "     |     PPO pur  •  aucun contrôleur caché  •  checkpoint initial / dernier / meilleur identifiables", 12);
            footer.style.marginTop = 14;
            root.Add(footer);

            // Style all buttons
            root.Query<Button>().ForEach(StyleButton);
            root.Query<VisualElement>(className: "unity-base-field__input").ForEach(input => {
                input.style.backgroundColor = new Color(.08f, .13f, .19f);
                input.style.color = new Color(.93f, .97f, 1f);
            });
            root.Query<Label>(className: "unity-base-field__label").ForEach(label => {
                label.style.minWidth = 90;
                label.style.width = 110;
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
            sep.style.backgroundColor = new Color(.18f, .26f, .35f);
            sep.style.marginTop = sep.style.marginBottom = 8;
            return sep;
        }

        static VisualElement Panel(float width)
        {
            var panel = new VisualElement();
            if (width > 0) { panel.style.width = width; panel.style.flexShrink = 0; }
            panel.style.backgroundColor = new Color(.045f, .075f, .115f, .96f);
            panel.style.paddingTop = panel.style.paddingBottom =
                panel.style.paddingLeft = panel.style.paddingRight = 18;
            panel.style.borderTopLeftRadius = panel.style.borderTopRightRadius = 10;
            panel.style.borderBottomLeftRadius = panel.style.borderBottomRightRadius = 10;
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
            button.style.height = 34;
            button.style.marginBottom = 6;
            button.style.backgroundColor = new Color(.08f, .23f, .3f);
            button.style.color = new Color(.91f, .98f, 1f);
            button.style.fontSize = 13;
            button.style.borderTopWidth = button.style.borderBottomWidth =
                button.style.borderLeftWidth = button.style.borderRightWidth = 0;
        }

        // -----------------------------------------------------------------------
        // Charts
        // -----------------------------------------------------------------------

        void DrawRewardChart(MeshGenerationContext ctx)
        {
            if (rewards.Count < 2) return;
            float min = Mathf.Min(rewards.ToArray()), max = Mathf.Max(rewards.ToArray());
            var p = ctx.painter2D;
            p.strokeColor = new Color(.12f, .83f, .9f);
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

        void DrawSuccessChart(MeshGenerationContext ctx)
        {
            if (successRates.Count < 1) return;
            float w = successChart.contentRect.width;
            float h = successChart.contentRect.height;
            var p = ctx.painter2D;
            // Draw the 18/20 = 0.9 target line.
            p.strokeColor = new Color(.2f, .75f, .2f, .4f);
            p.lineWidth = 1;
            p.BeginPath();
            float targetY = h * (1f - 0.9f);
            p.MoveTo(new Vector2(0, targetY));
            p.LineTo(new Vector2(w, targetY));
            p.Stroke();
            // Draw the success rate curve.
            if (successRates.Count < 2) return;
            p.strokeColor = new Color(.9f, .75f, .1f);
            p.lineWidth = 2;
            p.BeginPath();
            for (int i = 0; i < successRates.Count; i++)
            {
                var pt = new Vector2(i * w / (successRates.Count - 1), h * (1f - successRates[i]));
                if (i == 0) p.MoveTo(pt); else p.LineTo(pt);
            }
            p.Stroke();
            successRange.text = "Taux : " + (successRates[successRates.Count - 1] * 100).ToString("F0")
                + " %   •   " + successRates.Count + " évaluation(s)   •   Ligne verte = objectif 90 %";
        }
    }
}
