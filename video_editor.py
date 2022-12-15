import concurrent.futures
import moviepy.editor as mpye
from pydub import AudioSegment, effects
import time
import tempfile
import os
import itertools
import concurrent.futures

import utils.utils
import utils.audio
import utils.video


# Parameters
param = {
    "DEBUGGER_ARGUMENTS": ["last", "final_video.mp4"],
    # DEBUGGER_ARGUMENTS = ["last", "S4V6 Close Loop Control - Cruise Control.mp4", "--move"]
    "LOG_FILE": True,  # otherwise detect silence
    "EXTEND_LAST_FRAME": 0.15,
    # if lower than 1, % of extension
    # if 1, nothing
    # if greater than one, time in seconds
    # Audio modificaiton
    "NORMALISE_SOUND": True,
    "SILENCE_BETWEEN_SECTIONS": 0,  # milliseconds
    "START_VIDEO_SILENCE": 500,  # milliseconds
    "END_VIDEO_SILENCE": 1000,  # milliseconds
    # Part of the audio to silence (remove click sound)
    "SILENCE_PRE_MARGIN": 300,  # milliseconds
    "SILENCE_POST_MARGIN": 300,  # milliseconds
    # Audio fade immedidately after (pre) / before (post) silence
    "FADE_PRE_MARGIN": 100,  # milliseconds
    "FADE_POST_MARGIN": 100,  # milliseconds
    "MAX_SPEEDX": 5,  # times faster video
    "CROSSFADEIN_DURATION": 1.5,  # seconds
    "MISSING_IMAGE_TIMEOUT": int(5.0),  # seconds
    # Silence detection parameters
    "MIN_SILENCE_MS": 5000,
    "SILENCE_THRESHOLD_dB": -40,  # -16 / -40 OK
    # Colour palette
    "REMOVE_COLOUR_PALETTE": False,
    "REMOVE_COLOUR_PALETTE_INTERVAL": 1.0,  # seconds
}


def process_event(i, n_events, event, temp_folder, param):
    print(f"Processing: {i+1:2} / {n_events}")

    video = mpye.VideoFileClip(os.path.join(temp_folder, f"video_segment_{i}.mp4"))

    # Save last visual frame (for crossfade)
    image_path = os.path.join(temp_folder, f"last_visual_frame{i}.jpg")
    utils.utils.export_last_visual_frame(video, event, image_path)

    if event["mode"] == "raw":
        # It is necessary since the extracted video may be longer than expected
        video = video.subclip(0, event["both"][1] - event["both"][0])

        # Save video audio to file
        audio = video.audio
        temp_audio_file = os.path.join(temp_folder, f"temp_audio{i}.wav")
        if os.path.exists(temp_audio_file):
            os.remove(temp_audio_file)
        audio.write_audiofile(temp_audio_file)
        video_audio = AudioSegment.from_file(temp_audio_file, temp_audio_file[-3:])

        # Silence extreme parts
        audio_segment = video_audio[
            0
            + param["SILENCE_PRE_MARGIN"] : video.duration * 1000
            - param["SILENCE_POST_MARGIN"]
        ]

        audio_segment = (
            AudioSegment.silent(duration=param["SILENCE_PRE_MARGIN"])
            + audio_segment
            + AudioSegment.silent(duration=param["SILENCE_POST_MARGIN"])
        )

        # Normalize audio
        if param["NORMALISE_SOUND"]:
            audio_segment = effects.normalize(audio_segment)

        audio_segment_path = os.path.join(temp_folder, f"audio{i}.wav")
        audio_segment.export(audio_segment_path, format=audio_segment_path[-3:])

        audio_clip = mpye.AudioFileClip(audio_segment_path)
        video = video.set_audio(audio_clip)

    elif event["mode"] == "edit":
        # ----------------------- AUDIO EDITION ---------------------------------
        # Get non-silent (talking) audio segments
        talk = event["talk"]
        talk[0] -= event["draw"][0]  # relative to video segment start
        talk[1] -= event["draw"][0]  # relative to video segment start

        audio = video.audio
        temp_audio_file = os.path.join(temp_folder, f"temp_audio{i}.wav")
        if os.path.exists(temp_audio_file):
            os.remove(temp_audio_file)
        audio.write_audiofile(temp_audio_file)
        video_audio = AudioSegment.from_file(temp_audio_file, temp_audio_file[-3:])

        if param["NORMALISE_SOUND"]:
            video_audio = effects.normalize(video_audio)

        audio_segment = video_audio[
            talk[0] * 1000
            + param["SILENCE_PRE_MARGIN"] : talk[1] * 1000
            - param["SILENCE_POST_MARGIN"]
        ]

        audio_segment.fade_in(param["FADE_PRE_MARGIN"]).fade_out(
            param["FADE_POST_MARGIN"]
        )
        audio_segment = (
            AudioSegment.silent(duration=param["SILENCE_PRE_MARGIN"])
            + audio_segment
            + AudioSegment.silent(duration=param["SILENCE_POST_MARGIN"])
        )

        # Add Silence
        if i == 0:  # Video start
            audio_segment = (
                AudioSegment.silent(duration=param["START_VIDEO_SILENCE"])
                + audio_segment
            )
        audio_segment = audio_segment + AudioSegment.silent(
            duration=param["SILENCE_BETWEEN_SECTIONS"]
        )
        if i == n_events - 1:  # Video end
            audio_segment = audio_segment + AudioSegment.silent(
                duration=param["END_VIDEO_SILENCE"]
            )

        audio_segment_path = os.path.join(temp_folder, f"audio{i}.wav")
        audio_segment.export(audio_segment_path, format=audio_segment_path[-3:])

        audio_clip = mpye.AudioFileClip(audio_segment_path)

        # ----------------------- VIDEO EDITION ---------------------------------
        # Extract video files
        draw = [0, event["draw"][1] - event["draw"][0]]  # relative to splitted video
        video = video.subclip(draw[0], draw[1])

        # Video Modifications
        if param["REMOVE_COLOUR_PALETTE"]:
            print(f"{i} removing colour palette")
            video = utils.video.remove_colur_palette(
                video, param["REMOVE_COLOUR_PALETTE_INTERVAL"]
            )
            print(f"{i} removing colour palette - DONE")
        video = utils.video.extend_last_frame(video, param["EXTEND_LAST_FRAME"])

        # Speedup
        same_duration_ratio = video.duration / audio_clip.duration
        speedup_ratio = min(same_duration_ratio, param["MAX_SPEEDX"])
        print(f"{i} Speedup: {speedup_ratio:.2f}")
        video = video.fx(mpye.vfx.speedx, same_duration_ratio)
        # TODO: check if need to add silence to audio
        video = video.set_audio(audio_clip)

        # Mod frame time (fix Error: Index out of bound issue)
        frame_time = 1.0 / video.fps
        mod_frame_time = video.duration % frame_time
        if mod_frame_time != 0.0:
            video = video.subclip(t_end=video.duration - mod_frame_time)

    # Crossfade from last visual frame
    if i != 0:
        image_path = os.path.join(temp_folder, f"last_visual_frame{i-1}.jpg")
        for _ in range(param["MISSING_IMAGE_TIMEOUT"]):
            if os.path.exists(image_path):
                break
            time.sleep(1.0)
        else:
            raise Exception(f"Timeout: Missing image {i-1}")

        image_clip = mpye.ImageClip(image_path).set_duration(
            param["CROSSFADEIN_DURATION"]
        )

        video_crossfade = video.subclip(0, param["CROSSFADEIN_DURATION"])
        video_crossfade = video_crossfade.crossfadein(param["CROSSFADEIN_DURATION"])
        video_crossfade = mpye.CompositeVideoClip([image_clip, video_crossfade])
        video_crossfade.write_videofile(
            os.path.join(temp_folder, f"output{i}_crossfade.mp4")
        )

        video = video.subclip(t_start=param["CROSSFADEIN_DURATION"])

    video.write_videofile(os.path.join(temp_folder, f"output{i}.mp4"))
    print(f"{i} - COMPLETELY DONE")


if __name__ == "__main__":

    start = time.time()

    # Argument parser
    args = utils.utils.parse_arguments(param)
    abs_paths = utils.utils.process_arguments(args)

    # Import video file
    video = mpye.VideoFileClip(abs_paths["raw"])

    # Create folder
    temp_folder = os.path.join(tempfile.gettempdir(), "video_editing")
    if not os.path.exists(temp_folder):
        os.mkdir(temp_folder)

    # Clean temp folder
    for filename in os.listdir(temp_folder):
        file_path = os.path.join(temp_folder, filename)
        os.remove(file_path)

    if param["LOG_FILE"]:
        event_times = utils.utils.log2times(abs_paths["timestamp"], video.duration)
    else:
        # Save audio
        temp_audio_file = os.path.join(temp_folder, "temp_audio.wav")
        audio = video.audio
        if os.path.exists(temp_audio_file):
            os.remove(temp_audio_file)
        audio.write_audiofile(temp_audio_file)

        video_audio = AudioSegment.from_file(temp_audio_file, temp_audio_file[-3:])
        event_times = utils.audio.detect_silence(
            video_audio, param["MIN_SILENCE_MS"], param["SILENCE_THRESHOLD_dB"]
        )

    utils.utils.print_timestamps(event_times)

    # Split video into parts
    for i, event in enumerate(event_times):
        source = abs_paths["raw"]
        destination = os.path.join(temp_folder, f"video_segment_{i}.mp4")
        if event["mode"] == "raw":
            utils.video.extract_video(
                source, destination, event["both"][0], event["both"][1]
            )

        elif event["mode"] == "edit":
            utils.video.extract_video(
                source, destination, event["draw"][0], event["talk"][1]
            )
        else:
            raise Exception(f"Unkown event mode: {event['mode']}")

    print("------------------------------------------------------------------------")
    print("----------------------- START PARALLEL CALLS ---------------------------")
    print("------------------------------------------------------------------------")

    index = range(len(event_times))
    with concurrent.futures.ProcessPoolExecutor() as executor:
        executor.map(
            process_event,
            index,
            itertools.repeat(len(event_times)),
            event_times,
            itertools.repeat(temp_folder),
            itertools.repeat(param),
        )

    # Join video segments
    video_list = []
    for i in range(len(event_times)):
        if i != 0:
            video_list.append(os.path.join(temp_folder, f"output{i}_crossfade.mp4"))
        video_list.append(os.path.join(temp_folder, f"output{i}.mp4"))
    utils.video.concatenate_videos(video_list, abs_paths["edited"])

    if abs_paths["move"]:
        if args.output_file[0] != "S":
            print(f"Ouput video name: {args.output_file}")
            answer = input(
                "WARNING: Output video might be wrong do you want to continue?[y/N]\n"
            )
            if answer.lower() == "y":
                os.rename(abs_paths["raw"], abs_paths["raw_move"])
                os.rename(abs_paths["edited"], abs_paths["edit_move"])
                os.rename(abs_paths["timestamp"], abs_paths["timestamp_move"])

        os.rename(abs_paths["raw"], abs_paths["raw_move"])
        os.rename(abs_paths["edited"], abs_paths["edit_move"])
        os.rename(abs_paths["timestamp"], abs_paths["timestamp_move"])

    enlapsed_time = time.time() - start
    print(f"DONE in {time.time() - start:.1f} seconds ({enlapsed_time / 60:.1f} min)")
