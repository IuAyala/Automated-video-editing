import csv
import datetime
import os
import argparse
import sys

import io
import pstats
import cProfile

# Parameters
INPUT_EXTENSION = "mp4"


def profile(fnc):
    """A decorator that uses cProfile to profile a function"""

    def inner(*args, **kwargs):

        pr = cProfile.Profile()
        pr.enable()
        retval = fnc(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = "cumulative"
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
        return retval

    return inner


def parse_arguments(param):
    parser = argparse.ArgumentParser()
    parser.add_argument("video_file", help="Video file path")
    parser.add_argument(
        "output_file", help="Output video file name (include extension)"
    )
    parser.add_argument(
        "--move", action="store_true", help="Move files to the final folder"
    )
    if "pydevd" in sys.modules:
        args = parser.parse_args(param["DEBUGGER_ARGUMENTS"])
    else:
        args = parser.parse_args()

    return args


def process_arguments(args, display=True):
    # Folders
    obs_folder = "C:\\Users\\iuayala\\Videos\\OBS"
    course_folder = os.path.join(obs_folder, "Course")
    raw_video_folder = os.path.join(course_folder, "Raw Video")
    timestamps_folder = os.path.join(course_folder, "Timestamps")
    edited_video_folder = os.path.join(course_folder, "Edited Video")

    abs_paths = {
        "raw": None,
        "timestamp": os.path.join(obs_folder, "log.txt"),
        "edited": os.path.join(obs_folder, "final_video.mp4"),
        "raw_move": os.path.join(
            raw_video_folder, args.output_file[:-4] + " (Raw)" + args.output_file[-4:]
        ),
        "timestamp_move": os.path.join(timestamps_folder, args.output_file)[:-4]
        + ".txt",
        "edited_move": os.path.join(edited_video_folder, args.output_file),
        "move": args.move,
    }

    # Argument special case (get last video recorded)
    if args.video_file == "last":
        video_files = [
            f
            for f in os.listdir(obs_folder)
            if os.path.isfile(os.path.join(obs_folder, f))
            and f.endswith("." + INPUT_EXTENSION)
            and f[0].isnumeric()
        ]
        video_files = sorted(video_files)
        if not video_files:
            raise Exception(f"No file found with extension {INPUT_EXTENSION}")
        video_file = video_files[-1]
        abs_paths["raw"] = os.path.join(obs_folder, video_file)
    # Pass the whole name of the file to be processed
    elif args.video_file[0].isnumeric():
        video_file = args.video_file
        abs_paths["raw"] = os.path.join(obs_folder, video_file)
    # Pass SXVX format (i.e. S1V3)
    elif args.video_file[0] == "S" and args.video_file[2] == "V":
        abs_paths["raw"] = file_starts_with(raw_video_folder, args.video_file[:4])
        abs_paths["timestamp"] = file_starts_with(
            timestamps_folder, args.video_file[:4]
        )
        if not abs_paths["raw"]:
            raise Exception("Missing raw video - format SXVX")
        if not abs_paths["timestamp"]:
            raise Exception("Missing timestamps - format SXVX")

        abs_paths["edited"] = file_starts_with(edited_video_folder, args.video_file[:4])
        if not abs_paths["edited"]:
            print("Warning!: Missing output file - format SXVX")
            abs_paths["edited"] = os.path.join(edited_video_folder, args.video_file)

        if args.move:
            print("WARNIG!: Flagged to move, when it can't move!")
            abs_paths["move"] = False
    else:
        raise Exception("Unkwon video argument")

    if display:
        for key, value in abs_paths.items():
            print(f"{key:15}: {value}")

    return abs_paths


def log2times(log_file_path, video_duration):
    """Extracts the video edition information from a log file and converts it into an array of maps

    Args:
        log_file_path (str): path to log file where the video event information is contained
        video_duration (float): video duration in seconds

    Returns:
        list of dictionaries: each element of the list is a part of the final video either edited or raw (use the original video and audio)
    """
    output = []
    state = "stop"  # draw, talk, both, stop

    with open(log_file_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        for row in csv_reader:
            time_string, event = row
            date_time = datetime.datetime.strptime(time_string, "%H:%M:%S")
            a_timedelta = date_time - datetime.datetime(1900, 1, 1)
            time_seconds = a_timedelta.total_seconds()
            if event == "Event Draw":
                if state == "draw":  # Was draw now draw
                    output[-1]["draw"][0] = time_seconds
                elif state == "talk":  # Was talk now draw
                    output[-1]["talk"][1] = time_seconds
                    output.append(
                        {"mode": "edit", "draw": [time_seconds, -1], "talk": [-1, -1]}
                    )
                elif state == "both":  # Was both now draw
                    output[-1]["both"][1] = time_seconds
                    output.append(
                        {"mode": "edit", "draw": [time_seconds, -1], "talk": [-1, -1]}
                    )
                elif state == "stop":  # Was stop now draw
                    output.append(
                        {"mode": "edit", "draw": [time_seconds, -1], "talk": [-1, -1]}
                    )
                else:
                    raise Exception(f"Unknown state found: {state}")
                state = "draw"

            elif event == "Event Talk":
                if state == "draw":  # Was draw now talk
                    output[-1]["draw"][1] = time_seconds
                    output[-1]["talk"][0] = time_seconds
                elif state == "talk":  # Was talk now talk
                    output[-1]["talk"][0] = time_seconds
                elif state == "both":  # Was both now talk
                    output[-1]["both"][1] = time_seconds
                    raise Exception(
                        "Can't go directly from 'both' to 'talk', without 'draw' in between"
                    )
                elif state == "stop":  # Was stop now talk
                    if output[-1]["mode"] == "edit":
                        output[-1]["talk"][0] = time_seconds
                    else:
                        raise Exception("Can't use 'talk' without a previous 'draw'")
                else:
                    raise Exception(f"Unknown state found: {state}")
                state = "talk"

            elif event == "Event Both":
                if state == "draw":  # Was draw now both
                    output[-1]["draw"][1] = time_seconds
                    raise Exception(
                        "Can't go from 'draw' to 'both' without 'talk' in between"
                    )
                elif state == "talk":  # Was talk now both
                    output[-1]["talk"][1] = time_seconds
                    output.append({"mode": "raw", "both": [time_seconds, -1]})
                elif state == "both":  # Was both now both
                    output[-1]["both"][0] = time_seconds
                elif state == "stop":  # Was stop now both
                    output.append({"mode": "raw", "both": [time_seconds, -1]})
                else:
                    raise Exception(f"Unknown state found: {state}")
                state = "both"

            elif event == "Event Stop":
                if state == "draw":  # Was draw now stop
                    output[-1]["draw"][1] = time_seconds
                elif state == "talk":  # Was talk now stop
                    output[-1]["talk"][1] = time_seconds
                elif state == "both":  # Was both now stop
                    output[-1]["both"][1] = time_seconds
                elif state == "stop":  # Was stop now stop
                    pass
                else:
                    raise Exception(f"Unknown state found: {state}")
                state = "stop"

            else:
                print(f"WARNING: Unkown event: {event}")

        # Close last state
        if state == "draw":  # Was draw
            output[-1]["draw"][1] = video_duration
        elif state == "talk":  # Was talk
            output[-1]["talk"][1] = video_duration
        elif state == "stop":  # Was stop
            pass

    return output


def print_timestamps(event_times, width=6, precision=1):
    print("--------------- Timestamps ----------------")
    for el in event_times:
        if el["mode"] == "edit":
            print(
                f"Edit: Draw [{el['draw'][0]:{width}.{precision}f}, {el['draw'][1]:{width}.{precision}f}] - {el['draw'][1]-el['draw'][0]:{width}.{precision}f}"
            )
            print(
                f"Edit: Talk [{el['talk'][0]:{width}.{precision}f}, {el['talk'][1]:{width}.{precision}f}] - {el['talk'][1]-el['talk'][0]:{width}.{precision}f}"
            )
        elif el["mode"] == "raw":
            print(
                f"Raw : Both [{el['both'][0]:{width}.{precision}f}, {el['both'][1]:{width}.{precision}f}] - {el['both'][1]-el['both'][0]:{width}.{precision}f}"
            )
        else:
            print(f"WARNING: Unkown event mode {el['mode']}")
    print("-------------------------------------------")


def file_starts_with(folder, file_starts):
    """Retuns the absolute path of one file in a folder that starts with
    a certain string, if there is no match returns None

    Args:
        folder (string): folder absolute path
        file_starts (string): string to be matched

    Returns:
        string: absolute path of the file
    """
    for file in os.listdir(folder):
        abs_file_path = os.path.join(folder, file)
        if os.path.isfile(abs_file_path) and file.startswith(file_starts):
            return abs_file_path
    return None


def export_last_visual_frame(video, event, image_path):
    # Time of event is referenced to the whole video
    # But "video" is a subclip with only this section
    if event["mode"] == "raw":
        last_visual_frame_time = event["both"][1] - event["both"][0]
    elif event["mode"] == "edit":
        last_visual_frame_time = event["draw"][1] - event["draw"][0]

    video.save_frame(image_path, last_visual_frame_time)


if __name__ == "__main__":
    obs_folder = "C:\\Users\\iuayala\\Videos\\OBS"
    log_file_path = os.path.join(obs_folder, "log.txt")

    # Log file tests
    event_times = log2times(log_file_path, 100)
    print_timestamps(event_times)
