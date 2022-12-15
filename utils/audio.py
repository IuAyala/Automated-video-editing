import pydub


def detect_silence(video_audio, min_silence_ms, silence_threshold_db):
    print("INFO: Detecting silence...")
    silence_segments = pydub.silence.detect_silence(
        video_audio, min_silence_len=min_silence_ms, silence_thresh=silence_threshold_db
    )
    silence_seconds = [
        ((start / 1000), (stop / 1000)) for start, stop in silence_segments
    ]  # convert to sec

    # Extraced silence metrics and warnings
    if silence_seconds[0][0] != 0:
        print("WARNING!: First silence does NOT start at 0.0")

    output = []
    for i, el in enumerate(silence_seconds):
        output.append({"mode": "edit", "draw": [el[0], el[1]], "talk": [-1, -1]})
        if i == 0:
            previous_silence_end = el[1]
            continue

        output[i - 1]["talk"][0] = previous_silence_end
        output[i - 1]["talk"][1] = el[0]

        previous_silence_end = el[1]

    output[-1]["talk"][0] = previous_silence_end
    output[-1]["talk"][1] = len(video_audio) / 1000

    return output


def print_audio_info(video_audio):
    print(f"INFO: RMS (dB): {video_audio.dBFS:.2f}")
    print(f"INFO: Audio max dBFS: {video_audio.max_dBFS:.2f}")
    print(f"INFO: Audio duration: {video_audio.duration_seconds:.2f} seconds")