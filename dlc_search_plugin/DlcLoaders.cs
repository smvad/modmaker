using System;
using System.IO;
using BepInEx.Logging;
using UnityEngine;

namespace DlcRecursiveSearch;

/// <summary>
/// Direct loaders: read the indexed file wherever it lives and build the
/// Unity object ourselves. The vanilla loader (root-only File.ReadAllBytes)
/// is skipped via Harmony (prefix returns false) on success, so nothing is
/// ever copied into the game root.
/// </summary>
internal static class DlcLoaders
{
    private static ManualLogSource _log;

    public static void Init(ManualLogSource log) => _log = log;

    public static bool TryLoadSprite(string filePath, out Sprite sprite)
    {
        sprite = null;
        try
        {
            var bytes = File.ReadAllBytes(filePath);
            var tex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            // LoadImage is an extension in ImageConversionModule; fall back
            // to ImageConversion.LoadImage if the instance method is missing.
            bool ok = tex.LoadImage(bytes);
            if (!ok || tex.width <= 2 && tex.height <= 2 && bytes.Length > 100)
            {
                // LoadImage returns false on failure; tiny 2x2 with a big
                // file is also a failure signature. Fall through to warn.
                if (!ok)
                {
                    _log?.LogWarning($"LoadImage failed for '{filePath}'");
                    UnityEngine.Object.Destroy(tex);
                    return false;
                }
            }
            sprite = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0.5f));
            return sprite != null;
        }
        catch (Exception e)
        {
            _log?.LogWarning($"Sprite load failed for '{filePath}': {e.GetType().Name}: {e.Message}");
            sprite = null;
            return false;
        }
    }

    public static bool TryLoadAudio(string filePath, out AudioClip clip)
    {
        clip = null;
        try
        {
            var bytes = File.ReadAllBytes(filePath);
            if (!TryParseWav(bytes, out var samples, out var channels, out var frequency))
            {
                _log?.LogWarning($"WAV parse failed for '{filePath}' (need PCM 16-bit 44100 Hz)");
                return false;
            }
            clip = AudioClip.Create(Path.GetFileNameWithoutExtension(filePath), samples.Length / channels, channels, frequency, false);
            if (clip == null)
                return false;
            clip.SetData(samples, 0);
            return true;
        }
        catch (Exception e)
        {
            _log?.LogWarning($"Audio load failed for '{filePath}': {e.GetType().Name}: {e.Message}");
            clip = null;
            return false;
        }
    }

    /// <summary>
    /// Minimal WAV parser: PCM 8/16/24/32-bit + IEEE float, any rate/channels.
    /// Game content is PCM 16-bit 44100 Hz; other formats are converted to float.
    /// </summary>
    internal static bool TryParseWav(byte[] bytes, out float[] samples, out int channels, out int frequency)
    {
        samples = null;
        channels = 0;
        frequency = 0;
        try
        {
            if (bytes == null || bytes.Length < 44)
                return false;
            if (bytes[0] != 'R' || bytes[1] != 'I' || bytes[2] != 'F' || bytes[3] != 'F')
                return false;
            if (bytes[8] != 'W' || bytes[9] != 'A' || bytes[10] != 'V' || bytes[11] != 'E')
                return false;

            int pos = 12;
            int audioFormat = 0;
            int bitsPerSample = 0;
            int dataStart = -1;
            int dataLen = 0;

            while (pos + 8 <= bytes.Length)
            {
                string chunkId = System.Text.Encoding.ASCII.GetString(bytes, pos, 4);
                int chunkSize = BitConverter.ToInt32(bytes, pos + 4);
                if (chunkSize < 0 || pos + 8 + chunkSize > bytes.Length + 8)
                    break; // tolerate trailing garbage/padding
                if (chunkId == "fmt ")
                {
                    audioFormat = BitConverter.ToUInt16(bytes, pos + 8);
                    channels = BitConverter.ToUInt16(bytes, pos + 10);
                    frequency = BitConverter.ToInt32(bytes, pos + 12);
                    bitsPerSample = BitConverter.ToUInt16(bytes, pos + 22);
                }
                else if (chunkId == "data")
                {
                    dataStart = pos + 8;
                    dataLen = Math.Min(chunkSize, bytes.Length - dataStart);
                }
                pos += 8 + chunkSize;
                if ((chunkSize & 1) == 1) pos++; // word alignment
            }

            if (dataStart < 0 || channels <= 0 || frequency <= 0)
                return false;

            int bytesPerSample = bitsPerSample / 8;
            if (bytesPerSample <= 0)
                return false;
            int frames = dataLen / bytesPerSample / channels;
            if (frames <= 0)
                return false;

            samples = new float[frames * channels];
            for (int f = 0; f < frames; f++)
            {
                for (int c = 0; c < channels; c++)
                {
                    int off = dataStart + (f * channels + c) * bytesPerSample;
                    float v;
                    switch (bitsPerSample)
                    {
                        case 8:
                            v = (bytes[off] - 128) / 128f;
                            break;
                        case 16:
                            v = BitConverter.ToInt16(bytes, off) / 32768f;
                            break;
                        case 24:
                            int s24 = bytes[off] | (bytes[off + 1] << 8) | (bytes[off + 2] << 16);
                            if ((s24 & 0x800000) != 0) s24 |= unchecked((int)0xFF000000);
                            v = s24 / 8388608f;
                            break;
                        case 32 when audioFormat == 3:
                            v = BitConverter.ToSingle(bytes, off);
                            break;
                        case 32:
                            v = BitConverter.ToInt32(bytes, off) / 2147483648f;
                            break;
                        default:
                            return false;
                    }
                    samples[f * channels + c] = Math.Max(-1f, Math.Min(1f, v));
                }
            }
            return true;
        }
        catch
        {
            samples = null;
            return false;
        }
    }
}
