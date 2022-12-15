import moviepy.editor as mpe
from moviepy.video.compositing.concatenate import concatenate_videoclips
import subprocess
import os.path

# Down an right from top left
# Acquired by looking in Gimp with a frame that had the colour palette
PALETTE_INDEXES = [[440, 1530], [650, 1530], [440, 1890], [870, 1590]]


def active_colour_palette(np_frame):
    for down, right in PALETTE_INDEXES:
        pixel = np_frame[down, right]
        if pixel[0] == 255 and pixel[1] == 255 and pixel[2] == 255:
            return False
    return True


def remove_colur_palette(video, search_interval=1.0):
    """Removes colour palett from VideoClips, checks some predefined pixel values
    and if one of them is white then there is no colour palette, and viceversa

    Args:
        video (VideoClip): Video to be modified
        search_interval (float, optional): Interval at which the colour plaette will
                                           be searched for. Defaults to 1.0.

    Returns:
        VideoClip: Video without colour palette
    """
    current_time = 0
    palette_intervals = []
    previous_active = False
    while current_time < video.duration:
        np_frame = video.get_frame(current_time)  # time in seconds
        active = active_colour_palette(np_frame)
        if not previous_active and active:  # color palette opened
            palette_intervals.append([max(current_time - search_interval, 0), -1])
        if previous_active and not active:  # color palette closed
            palette_intervals[-1][1] = min(
                current_time + search_interval, video.duration
            )

        previous_active = active
        current_time += search_interval

    if previous_active:
        palette_intervals[-1][1] = video.duration

    for start, stop in reversed(palette_intervals):
        video = video.cutout(start, stop)

    return video


def extend_last_frame(video, extend_value):
    """Extends the last frame of the video by a certain amount

    Args:
        video (VideoClip): Video to be extended
        extend_value (float):
            If this value is 1.0 then the same video is returned
            If this value is smaller than one, this is the % of extension of the video duration
            If this value is greater than 1.0, then this is the duration of the extension in seconds

    Returns:
        VideoClip: Extended VideoClip
    """
    if extend_value == 1.0:
        return video

    last_frame = video.get_frame(video.duration - 0.1)
    if extend_value > 1.0:
        extension_duration = extend_value
    else:
        extension_duration = video.duration * extend_value

    extension_video = mpe.ImageClip(last_frame, duration=extension_duration)
    extended_video = concatenate_videoclips([video, extension_video])

    return extended_video


def extract_video(source, destination, t_beg, t_end, debug=False):
    """Extracts video segments from bigger videos, leaving the original video unaltered

    Args:
        source (string): path of the video source
        destination (string): path of the video destination (including extension)
        t_beg (int): beginning time of the video to be extracted
        t_end (int): end time of the video to be extracted

    """
    command = [
        "ffmpeg",
        "-y",  # overwrite
        "-ss",
        f"{t_beg}",  # start time
        "-t",
        f"{t_end}",  # end time
        "-i",
        f"{source}",  # source video file path
        "-acodec",  # audio codec
        "copy",
        "-vcodec",  # vvideo codec
        "copy",
        f"{destination}",  # output video file path
    ]

    if debug:
        buf = None  # print to terminal
    else:
        buf = subprocess.DEVNULL

    subprocess.call(command, shell=True, stdout=buf, stderr=buf)


def concatenate_videos(video_list, output, debug=False):
    """Concatenate a list of videos with the same encoding (very fast!)

    Args:
        video_list (list of strings): list of paths to each video to be concatenated
        output (string): path to the output video
    """
    last_backslash = video_list[0].rfind("\\")
    temp_folder = video_list[0][:last_backslash]

    # Create text file
    video_list_path = os.path.join(temp_folder, "vidlist.txt")
    with open(video_list_path, "w") as file:
        for video in video_list:
            file.write(f"file '{video}'\n")

    # Concatenate ffmpeg command
    command = [
        "ffmpeg",
        "-y",  # overwrite
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        f"{video_list_path}",
        "-c",
        "copy",
        f"{output}",
    ]

    if debug:
        buf = None  # print to terminal
    else:
        buf = subprocess.DEVNULL

    subprocess.call(command, shell=True, stdout=buf, stderr=buf)


if __name__ == "__main__":
    import os
    from moviepy.editor import VideoFileClip
    import tempfile

    video_list = []
    temp_folder = os.path.join(tempfile.gettempdir(), "video_editing")
    for i in range(3):
        video_list.append(os.path.join(temp_folder, f"video_segment_{i}.mp4"))
    concatenate_videos(video_list, os.path.join(temp_folder, "test.mp4"))

    """
    obs_folder = "C:\\Users\\iuayala\\Videos\\OBS"

    video_file = os.path.join(obs_folder, "1S4V1 - Why Learn Control Theory (Raw).mp4")
    video = VideoFileClip(video_file)

    # extend_last_frame test
    video = extend_last_frame(video, 0.1)
    video.write_videofile(os.path.join(obs_folder, "test.mp4"))

    # remove_colour_palette test
    remove_colur_palette(video)
    """
