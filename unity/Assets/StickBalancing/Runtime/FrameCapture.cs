using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace StickBalancing
{
    // Explicit developer capture of real rendered frames for documentation.
    public sealed class FrameCapture : MonoBehaviour
    {
        [Serializable] class CaptureRecord { public string source = "actual Unity rendered frames"; public float[] simulated_seconds; }
        IEnumerator Start()
        {
            var args = Environment.GetCommandLineArgs();
            int option = Array.IndexOf(args, "--capture-dir");
            if (option < 0 || option + 1 >= args.Length) yield break;
            string directory = Path.GetFullPath(args[option + 1]);
            Directory.CreateDirectory(directory);
            int count = 1;
            int countOption = Array.IndexOf(args, "--capture-count");
            if (countOption >= 0 && countOption + 1 < args.Length) count = Mathf.Clamp(int.Parse(args[countOption + 1]), 1, 300);
            yield return new WaitForSecondsRealtime(3);
            var record = new CaptureRecord { simulated_seconds = new float[count] };
            for (int i = 0; i < count; i++) {
                yield return new WaitForEndOfFrame();
                record.simulated_seconds[i] = Time.fixedTime;
                var texture = ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(directory, i.ToString("D4") + ".png"), texture.EncodeToPNG());
                Destroy(texture);
                yield return new WaitForSecondsRealtime(.1f);
            }
            File.WriteAllText(Path.Combine(directory, "frames.json"), JsonUtility.ToJson(record, true));
            if (Array.IndexOf(args, "--quit-after-capture") >= 0) Application.Quit();
        }
    }
}
