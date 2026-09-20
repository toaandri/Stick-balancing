using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using UnityEngine.UIElements;

namespace StickBalancing.Editor
{
    public static class BuildPrototype
    {
        // -----------------------------------------------------------------
        // Scene creation helpers
        // -----------------------------------------------------------------

        static void CreateWorkerScene(int segments)
        {
            EnsureMaterials();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var agentGO = new GameObject("Swing-up environment");
            agentGO.SetActive(false);
            var behavior = agentGO.AddComponent<BehaviorParameters>();
            behavior.BehaviorName = $"StickBalancingN{segments}";
            behavior.BehaviorType = BehaviorType.Default;
            // observation_size = 2 + 3 * segments
            behavior.BrainParameters.VectorObservationSize = 2 + 3 * segments;
            behavior.BrainParameters.NumStackedVectorObservations = 1;
            behavior.BrainParameters.ActionSpec = ActionSpec.MakeContinuous(1);
            var agent = agentGO.AddComponent<SwingUpAgent>();
            agent.task = new TaskContract { segments = segments };
            agentGO.AddComponent<DecisionRequester>().DecisionPeriod = 5;
            agentGO.AddComponent<FrameCapture>();
            agentGO.SetActive(true);
            var camera = new GameObject("Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(0, 2, -7);
            camera.transform.rotation = Quaternion.identity;
            camera.backgroundColor = new Color(.04f, .07f, .12f);
            camera.clearFlags = CameraClearFlags.SolidColor;
            var light = new GameObject("Light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(40, -30, 0);
        }

        // -----------------------------------------------------------------
        // Menu items — individual scenes
        // -----------------------------------------------------------------

        [MenuItem("Stick Balancing/Create phase-0 scene (N=1)")]
        public static void CreateSceneN1() => CreateAndSaveWorkerScene(1);

        [MenuItem("Stick Balancing/Create scene N=2")]
        public static void CreateSceneN2() => CreateAndSaveWorkerScene(2);

        [MenuItem("Stick Balancing/Create scene N=3")]
        public static void CreateSceneN3() => CreateAndSaveWorkerScene(3);

        static void CreateAndSaveWorkerScene(int segments)
        {
            CreateWorkerScene(segments);
            Directory.CreateDirectory("Assets/Scenes");
            string path = segments == 1 ? "Assets/Scenes/Prototype.unity"
                : $"Assets/Scenes/PrototypeN{segments}.unity";
            EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), path);
        }

        // Keep legacy name for backward-compatible script references.
        [MenuItem("Stick Balancing/Create phase-0 scene")]
        public static void CreateScene() => CreateAndSaveWorkerScene(1);

        // -----------------------------------------------------------------
        // Build methods called from PowerShell (batch mode)
        // -----------------------------------------------------------------

        static void EnsureVersion()
        {
            if (Application.unityVersion != "6000.0.60f1")
                throw new InvalidOperationException(
                    "Use Unity 6000.0.60f1 or revalidate the toolchain first");
        }

        /// <summary>Build the N=1 headless worker (default batch target).</summary>
        public static void Windows() => BuildWorker(1);

        /// <summary>Build the N=2 headless worker.</summary>
        public static void WindowsN2() => BuildWorker(2);

        /// <summary>Build the N=3 headless worker.</summary>
        public static void WindowsN3() => BuildWorker(3);

        static void BuildWorker(int segments)
        {
            EnsureVersion();
            CreateAndSaveWorkerScene(segments);
            ApplyCommonPlayerSettings();
            PlayerSettings.productName = $"StickBalancing Prototype N={segments}";
            string suffix = segments == 1 ? "" : $"N{segments}";
            string output = Path.GetFullPath(
                $"../builds/windows/worker/StickBalancingWorker{suffix}.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            string scenePath = segments == 1 ? "Assets/Scenes/Prototype.unity"
                : $"Assets/Scenes/PrototypeN{segments}.unity";
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { scenePath },
                target = BuildTarget.StandaloneWindows64,
                locationPathName = output,
                options = BuildOptions.None
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException(
                    $"Unity Worker N={segments} build failed: {report.summary.result}");
        }

        /// <summary>Build the desktop application (UI + preview).</summary>
        public static void Desktop()
        {
            EnsureMaterials();
            EnsureVersion();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Directory.CreateDirectory("Assets/Scenes");
            var camera = new GameObject("Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(0, 1.8f, -7);
            camera.backgroundColor = new Color(.025f, .045f, .075f);
            camera.clearFlags = CameraClearFlags.SolidColor;
            var light = new GameObject("Light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(40, -30, 0);
            new GameObject("Preview").AddComponent<PendulumPreview>();
            var panel = AssetDatabase.LoadAssetAtPath<PanelSettings>(
                "Assets/Scenes/DesktopPanel.asset");
            if (panel == null)
            {
                panel = ScriptableObject.CreateInstance<PanelSettings>();
                AssetDatabase.CreateAsset(panel, "Assets/Scenes/DesktopPanel.asset");
            }
            panel.themeStyleSheet = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(
                "Assets/StickBalancing/Runtime/RuntimeTheme.tss");
            panel.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            panel.referenceResolution = new Vector2Int(1440, 900);
            new GameObject("Desktop").AddComponent<DesktopApp>().panelSettings = panel;
            new GameObject("Documentation capture").AddComponent<FrameCapture>();
            EditorUtility.SetDirty(panel);
            AssetDatabase.SaveAssets();
            EditorSceneManager.SaveScene(
                EditorSceneManager.GetActiveScene(), "Assets/Scenes/Desktop.unity");
            ApplyCommonPlayerSettings();
            PlayerSettings.productName = "StickBalancing RL";
            PlayerSettings.defaultScreenWidth = 1440;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            var output = Path.GetFullPath("../builds/windows/app/StickBalancing.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { "Assets/Scenes/Desktop.unity" },
                target = BuildTarget.StandaloneWindows64,
                locationPathName = output,
                options = BuildOptions.None
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException("Desktop build failed");
        }

        static void ApplyCommonPlayerSettings()
        {
            PlayerSettings.companyName = "StickBalancing";
            PlayerSettings.runInBackground = true;
            PlayerSettings.SetScriptingBackend(
                UnityEditor.Build.NamedBuildTarget.Standalone,
                ScriptingImplementation.Mono2x);
        }

        static void EnsureMaterials()
        {
            Directory.CreateDirectory("Assets/Resources");
            AssetDatabase.Refresh();
            if (AssetDatabase.LoadAssetAtPath<Material>("Assets/Resources/StickSurface.mat") == null)
            {
                var material = new Material(Shader.Find("Standard"));
                material.color = new Color(.3f, .4f, .5f);
                material.SetFloat("_Metallic", .35f);
                material.SetFloat("_Glossiness", .55f);
                AssetDatabase.CreateAsset(material, "Assets/Resources/StickSurface.mat");
            }
        }
    }
}
