import copy
import enum
import os
import math
import random
import numpy as np
import cv2 as cv
from ffpyplayer.player import MediaPlayer
import tkinter as tk
from tkinter import filedialog


########################################################################################################################
# Utility functions ####################################################################################################
########################################################################################################################
# Return a list of filepaths in a directory that match on any of the extensions.
# If recursive, include any matches in all subdirectories.
def get_files(directory, extensions, recursive=False):
    matched_files = []
    if not os.path.isdir(directory) or len(extensions) == 0:
        return matched_files

    def match_files(collection, root):
        for file in collection:
            name, ext = os.path.splitext(file)
            if ext in extensions:
                matched_files.append(os.path.join(root, file))

    if recursive:
        for subdir, _, files in os.walk(directory):
            match_files(files, subdir)
    else:
        match_files(os.listdir(directory), directory)

    return matched_files

# Given a time interval expressed in seconds, convert to a tuple of (hours, minutes, seconds, milliseconds)
def get_hours_minutes_seconds_milliseconds_from_seconds(seconds):
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    milliseconds = 1000 * (seconds - math.floor(seconds))
    seconds = math.floor(seconds)
    return hours, minutes, seconds, milliseconds

# Given a tuple of (hours, minutes, seconds, milliseconds), return a time string formatted by "HH:MM:SS:MSS".
def get_time_format_string_from_hh_mm_ss_ms(hours, minutes, seconds, milliseconds):
    if hours > 0:
        time_format_string = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{int(milliseconds):03d}"
    else:
        time_format_string = f"{int(minutes):02d}:{int(seconds):02d}.{int(milliseconds):03d}"
    return time_format_string

# Given a time interval expressed in seconds, return a time string formatted by "HH:MM:SS:MSS".
def get_time_format_string_from_seconds(seconds):
    return get_time_format_string_from_hh_mm_ss_ms(*get_hours_minutes_seconds_milliseconds_from_seconds(seconds))
########################################################################################################################

# Video filtering options
class VideoFilter(enum.IntEnum):
        NO_FILTER = 0,
        MONOCHROME = 1,
        VALUE_INVERT = 2,
        RED_FILTER = 3,
        GREEN_FILTER = 4,
        BLUE_FILTER = 5,
        YELLOW_FILTER = 6,
        CYAN_FILTER = 7,
        MAGENTA_FILTER = 8,
        SWAP_RED_GREEN = 9,
        SWAP_GREEN_BLUE = 10,
        SWAP_BLUE_RED = 11,
        CYCLE_BLUE_GREEN_RED_ONCE = 12,
        CYCLE_BLUE_GREEN_RED_TWICE = 13
        BGR_TO_HSV = 14,
        RGB_TO_HSV = 15,
        HSV_TO_BGR = 16,
        HSV_TO_RGB = 17,
        BGR_TO_HLS = 18,
        RGB_TO_HLS = 19,
        HLS_TO_BGR = 20,
        HLS_TO_RGB = 21,
        BGR_TO_LAB = 22,
        RGB_TO_LAB = 23,
        LAB_TO_BGR = 24,
        LAB_TO_RGB = 25,
        BGR_TO_LUV = 26,
        RGB_TO_LUV = 27,
        LUV_TO_BGR = 28,
        LUV_TO_RGB = 29,

        FILTER_COUNT = 30


class VideoPlayer:
    def __init__(self, directory=None, extensions=[".mp4", ".mov"], recursive=False):
        self.extensions = extensions
        self.abort_key = ''
        self.with_audio = False
        self.audio_volume = 1.0
        self.loop_mode = False
        self.is_paused = False
        self.is_muted = False
        self.video_filter = VideoFilter.NO_FILTER

        self.video_files = None
        self.load_videos(directory, extensions=extensions, recursive=recursive)
        self.video_file = None
        self.frame = None
        self.frame_unfiltered = None
        self.frame_width = 0
        self.frame_height = 0

        self.video_capture = None

        self.favorites_map = {}

        self.speed_factors = [1.0, 2.0, 4.0, 8.0, 16.0, 0.0625, 0.125, 0.25, 0.5]
        self.speed_factor_index = 0



    # Print a string with relevant video properties: width and height in pixels, fps, current frame number,
    # total frame count, current time in hh:mm:ss.mss and total time in hh:mm:ss.ms
    def print_basic_video_properties(self):
        if self.video_capture is None:
            return
        if not self.video_capture.isOpened():
            return

        fps = self.video_capture.get(cv.CAP_PROP_FPS)
        frame_count = self.video_capture.get(cv.CAP_PROP_FRAME_COUNT)
        frame_count_digits = math.floor(math.log(frame_count, 10)) + 1

        # Get total and current time in seconds
        total_time = frame_count / fps
        current_time = self.video_capture.get(cv.CAP_PROP_POS_MSEC) / 1000.0

        # Video properties: width, height, current frame number
        width, height = int(self.video_capture.get(cv.CAP_PROP_FRAME_WIDTH)), int(
            self.video_capture.get(cv.CAP_PROP_FRAME_HEIGHT))
        frame_position = int(self.video_capture.get(cv.CAP_PROP_POS_FRAMES))

        # Compute time format strings
        current_time_format_string = get_time_format_string_from_seconds(current_time)
        total_time_format_string = get_time_format_string_from_seconds(total_time)

        print(f'{width}x{height}, {fps:0.2f} fps | {frame_position:0{frame_count_digits}d}/{int(frame_count)} | '
              f'{current_time_format_string}/{total_time_format_string}')

    def load_videos(self, directory, extensions=[".mov", ".mp4"], recursive=False):
        if directory is None:
            return
        if not os.path.isdir(directory):
            return
        self.video_files = get_files(directory, extensions=extensions, recursive=recursive)
        return len(self.video_files) > 0

    def filter_frame(self, frame):
        if self.video_filter == VideoFilter.MONOCHROME:
            frame = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        elif self.video_filter == VideoFilter.VALUE_INVERT:
            frame = 255 - frame
        elif self.video_filter == VideoFilter.RED_FILTER:
            filter_mask = np.array([0, 0, 1], dtype=np.uint8)
            filter_matrix = np.full((int(self.frame_height), int(self.frame_width), 3), filter_mask, dtype=np.uint8)
            frame *= filter_matrix
        elif self.video_filter == VideoFilter.GREEN_FILTER:
            filter_mask = np.array([0, 1, 0], dtype=np.uint8)
            filter_matrix = np.full((int(self.frame_height), int(self.frame_width), 3), filter_mask, dtype=np.uint8)
            frame *= filter_matrix
        elif self.video_filter == VideoFilter.BLUE_FILTER:
            filter_mask = np.array([1, 0, 0], dtype=np.uint8)
            filter_matrix = np.full((int(self.frame_height), int(self.frame_width), 3), filter_mask, dtype=np.uint8)
            frame *= filter_matrix
        elif self.video_filter == VideoFilter.YELLOW_FILTER:
            filter_mask = np.array([0, 1, 1], dtype=np.uint8)
            filter_matrix = np.full((int(self.frame_height), int(self.frame_width), 3), filter_mask, dtype=np.uint8)
            frame *= filter_matrix
        elif self.video_filter == VideoFilter.CYAN_FILTER:
            filter_mask = np.array([1, 1, 0], dtype=np.uint8)
            filter_matrix = np.full((int(self.frame_height), int(self.frame_width), 3), filter_mask, dtype=np.uint8)
            frame *= filter_matrix
        elif self.video_filter == VideoFilter.MAGENTA_FILTER:
            filter_mask = np.array([1, 0, 1], dtype=np.uint8)
            filter_matrix = np.full((int(self.frame_height), int(self.frame_width), 3), filter_mask, dtype=np.uint8)
            frame *= filter_matrix
        elif self.video_filter == VideoFilter.SWAP_RED_GREEN:
            frame[:, :, [1, 2]] = frame[:, :, [2, 1]]
        elif self.video_filter == VideoFilter.SWAP_GREEN_BLUE:
            frame[:, :, [0, 1]] = frame[:, :, [1, 0]]
        elif self.video_filter == VideoFilter.SWAP_BLUE_RED:
            frame[:, :, [0, 2]] = frame[:, :, [2, 0]]
        elif self.video_filter == VideoFilter.CYCLE_BLUE_GREEN_RED_ONCE:
            frame[:, :, [0, 1]] = frame[:, :, [1, 0]]
            frame[:, :, [1, 2]] = frame[:, :, [2, 1]]
        elif self.video_filter == VideoFilter.CYCLE_BLUE_GREEN_RED_TWICE:
            frame[:, :, [0, 1]] = frame[:, :, [1, 0]]
            frame[:, :, [0, 2]] = frame[:, :, [2, 0]]
        elif self.video_filter == VideoFilter.BGR_TO_HSV:
            frame = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
        elif self.video_filter == VideoFilter.RGB_TO_HSV:
            frame = cv.cvtColor(frame, cv.COLOR_RGB2HSV)
        elif self.video_filter == VideoFilter.HSV_TO_BGR:
            frame = cv.cvtColor(frame, cv.COLOR_HSV2BGR)
        elif self.video_filter == VideoFilter.HSV_TO_RGB:
            frame = cv.cvtColor(frame, cv.COLOR_HSV2RGB)
        elif self.video_filter == VideoFilter.BGR_TO_HLS:
            frame = cv.cvtColor(frame, cv.COLOR_BGR2HLS)
        elif self.video_filter == VideoFilter.RGB_TO_HLS:
            frame = cv.cvtColor(frame, cv.COLOR_HLS2BGR)
        elif self.video_filter == VideoFilter.HLS_TO_BGR:
            frame = cv.cvtColor(frame, cv.COLOR_HLS2BGR)
        elif self.video_filter == VideoFilter.HLS_TO_RGB:
            frame = cv.cvtColor(frame, cv.COLOR_HLS2RGB)
        elif self.video_filter == VideoFilter.BGR_TO_LAB:
            frame = cv.cvtColor(frame, cv.COLOR_BGR2LAB)
        elif self.video_filter == VideoFilter.RGB_TO_LAB:
            frame = cv.cvtColor(frame, cv.COLOR_RGB2LAB)
        elif self.video_filter == VideoFilter.LAB_TO_BGR:
            frame = cv.cvtColor(frame, cv.COLOR_LAB2BGR)
        elif self.video_filter == VideoFilter.LAB_TO_RGB:
            frame = cv.cvtColor(frame, cv.COLOR_LAB2RGB)
        elif self.video_filter == VideoFilter.BGR_TO_LUV:
            frame = cv.cvtColor(frame, cv.COLOR_BGR2LUV)
        elif self.video_filter == VideoFilter.RGB_TO_LUV:
            frame = cv.cvtColor(frame, cv.COLOR_RGB2LUV)
        elif self.video_filter == VideoFilter.LUV_TO_BGR:
            frame = cv.cvtColor(frame, cv.COLOR_LUV2BGR)
        elif self.video_filter == VideoFilter.LUV_TO_RGB:
            frame = cv.cvtColor(frame, cv.COLOR_LUV2RGB)
        return frame

    # Play a video file
    # Optionally pass a favorites map that associates key presses with video files
    # Favorites feature: when you press a key that's not otherwise mapped to a function like pausing, going to the next
    # video, restarting, etc., the first press will save the video as a favorite associated with the key. Any subsequent
    # press of this key will recall the saved video.
    def play_video(self):
        print(f"Playing {self.video_file}.")
        self.video_capture = cv.VideoCapture(self.video_file)
        if self.with_audio:
            audio_capture = MediaPlayer(self.video_file, ff_opts={'sync': 'video'})
            is_initial_volume_set = False
            if self.is_muted:
                audio_capture.set_mute(1)
                initial_volume = 0.0
            else:
                audio_capture.set_mute(0)
                initial_volume = self.audio_volume

        fps = self.video_capture.get(cv.CAP_PROP_FPS)
        frame_time_ms = int(1000.0 / fps)
        total_time_ms = 1000 * self.video_capture.get(cv.CAP_PROP_FRAME_COUNT) / fps
        self.frame_width = self.video_capture.get(cv.CAP_PROP_FRAME_WIDTH)
        self.frame_height = self.video_capture.get(cv.CAP_PROP_FRAME_HEIGHT)

        self.abort_key = ''
        jump_time = None
        jump_time_format_string = ''
        user_request = False
        initial_frame = True

        self.print_basic_video_properties()
        if self.video_filter != VideoFilter.NO_FILTER:
            print(f"Filter set to {VideoFilter(self.video_filter).name.replace('_', ' ')}")

        while True:
            if not self.is_paused or initial_frame:
                # Get current video frame
                ret, frame = self.video_capture.read()
                self.frame_unfiltered = frame
                initial_frame = False

                if self.with_audio:
                    # Get current audio frame
                    audio_frame, val = audio_capture.get_frame()

                    # Set initial volume
                    if not is_initial_volume_set and audio_frame is not None:
                        audio_capture.set_volume(initial_volume)
                        is_initial_volume_set = True

                    # Handle audio EOF
                    if val == 'eof' and audio_frame is None:
                        audio_capture.close_player()

                # Handle video EOF
                if not ret:
                    if self.loop_mode:
                        if self.with_audio:
                            # Audio player must be closed and re-opened since we hit EOF
                            audio_capture.close_player()
                            audio_capture = MediaPlayer(self.video_file, ff_opts={'sync': 'video'})
                            audio_frame, val = audio_capture.get_frame()

                        # Seek back to the start of video
                        self.video_capture.set(cv.CAP_PROP_POS_MSEC, 0)
                        ret, frame = self.video_capture.read()

                    else:
                        # End of video
                        break

                # Filter frame
                frame_filtered = self.filter_frame(copy.deepcopy(self.frame_unfiltered))

                # Resize video frame
                # frame_filtered = cv.resize(frame_filtered, None, fx=0.5, fy=0.5, interpolation=cv.INTER_LINEAR)

                cv.imshow('', frame_filtered)

            # Handle user input
            wait_key = cv.waitKey(frame_time_ms) & 0xFF
            wait_key_chr = chr(wait_key)

            # Press 'q' exit. Press 'n' for next video.
            if wait_key_chr == 'q' or wait_key_chr == 'n':
                self.abort_key = chr(wait_key)
                print("Aborting.") if wait_key_chr == 'q' else print("Next video...")
                break

            # Press 'l' for loop mode toggle
            elif wait_key_chr == 'l':
                self.loop_mode = not self.loop_mode
                print(f"Loop mode {'on' if self.loop_mode else 'off'}.")
            # Press backspace to jump to start of video
            elif wait_key_chr == '\b':
                # Restart the video
                self.video_capture.set(cv.CAP_PROP_POS_MSEC, 0)
                if self.with_audio:
                    audio_capture.seek(0, relative=False, seek_by_bytes=False, accurate=True)
                print("Restarting video.")

            # Press 't' to set a time to jump back to with 'j'
            elif wait_key_chr == 't':
                jump_time = self.video_capture.get(cv.CAP_PROP_POS_MSEC)
                jump_time_format_string = get_time_format_string_from_seconds(jump_time / 1000.0)
                print(f"Jump time set to {jump_time_format_string}")
            # Press 'j' to jump back to the time set by 't'
            elif wait_key_chr == 'j':
                if jump_time is not None:
                    # Return to jump point
                    self.video_capture.set(cv.CAP_PROP_POS_MSEC, jump_time)
                    print(f"Jumping back to {jump_time_format_string}")

            # Press 'p' to pause
            elif wait_key_chr == 'p':
                self.is_paused = not self.is_paused
                if self.with_audio:
                    audio_capture.set_pause(self.is_paused)
                print(f"Playback {'' if self.is_paused else 'un'}paused.")

            # Press 'm' to mute audio
            elif wait_key_chr == 'm':
                if self.with_audio:
                    # Toggle mute control
                    self.is_muted = not self.is_muted
                    # Set audio volume
                    audio_capture.set_volume(0) if self.is_muted else audio_capture.set_volume(self.audio_volume)
                    # Won't do jack shit
                    # audio_capture.set_mute(1) if self.is_muted else audio_capture.set_mute(0)
                    print("Audio muted.") if self.is_muted else print("Audio unmuted.")

            # Press '+' to increment audio volume by 0.1. Press '-' to decrement audio volume by 0.1.
            elif wait_key_chr == '-' or wait_key_chr == '+':
                if self.with_audio:
                    increment = -0.1 if wait_key_chr == '-' else 0.1
                    self.audio_volume = round(min(1.0, max(0.0, self.audio_volume + increment)), 2)
                    audio_capture.set_volume(self.audio_volume)
                    print(f"Audio volume set to {self.audio_volume}.")

            # Press 'r' to rewind 1 second, scaled by the current speed multiplier.
            # Press 'R' to rewind 5 seconds, scaled by the current speed multiplier.
            # Press 'f'/'F' similarly to fast-forward.
            elif wait_key_chr == 'f' or wait_key_chr == 'F' or wait_key_chr == 'r' or wait_key_chr == 'R':
                speed_multiplier = self.speed_factors[self.speed_factor_index]
                if wait_key_chr == 'f':
                    seek_time = 1.0 * speed_multiplier
                elif wait_key_chr == 'F':
                    seek_time = 5.0 * speed_multiplier
                elif wait_key_chr == 'r':
                    seek_time = -1.0 * speed_multiplier
                else:
                    seek_time = -5.0 * speed_multiplier

                # Calculate position to seek to
                video_position_ms = self.video_capture.get(cv.CAP_PROP_POS_MSEC)
                frame_to_seek_ms = video_position_ms + 1000.0 * seek_time
                frame_to_seek_ms = min(max(0, frame_to_seek_ms), total_time_ms)
                frame_to_seek_time_string = get_time_format_string_from_seconds(frame_to_seek_ms / 1000.0)

                self.video_capture.set(cv.CAP_PROP_POS_MSEC, frame_to_seek_ms)
                if self.with_audio:
                    audio_capture.seek(frame_to_seek_ms / 1000.0, relative=False, seek_by_bytes=False, accurate=True)
                print(f"Seeking {'+' if seek_time > 0 else ''}{seek_time:0.3}s to {frame_to_seek_time_string}.")

            # Press 's' to speed up or 'd' to slow down in a cycle of
            # (200%, 400%, 800%, 1600%, 6.25%, 12.5%, 25%, 50%, 100%)
            # (2x, 4x, 8x, 16x, 0.0625x, 0.125x, 0.25x, 0.5x, 1x)
            # Videos start at 100% speed by default
            elif wait_key_chr == 's' or wait_key_chr == 'd':
                speed_factor_increment = 1 if wait_key_chr == 'd' else -1
                self.speed_factor_index = (self.speed_factor_index + speed_factor_increment) % len(self.speed_factors)
                speed_multiplier = self.speed_factors[self.speed_factor_index]

                new_fps = speed_multiplier * fps
                frame_time_ms = int(1000.0 / new_fps)
                self.video_capture.set(cv.CAP_PROP_FPS, new_fps)
                print(f"Setting speed to {speed_multiplier:0.3}x = {new_fps:0.3} fps.")

            # Press 'a' to restore both speed up and slow down cycles to 100% and remove filter
            elif wait_key_chr == 'a':
                self.speed_factor_index = 0
                frame_time_ms = int(1000.0 / fps)
                self.video_filter = VideoFilter.NO_FILTER
                self.video_capture.set(cv.CAP_PROP_SPEED, fps)
                print(f"Restoring normal speed 1.0x = {fps:0.3} fps and removing filter.")

            # Press 'y' to increment filter. Press 'u' to decrement filter.
            elif wait_key_chr == 'y' or wait_key_chr == 'u':
                filter_increment = 1 if wait_key_chr == 'y' else -1
                self.video_filter = (self.video_filter + filter_increment) % VideoFilter.FILTER_COUNT
                if self.is_paused:
                    frame_filtered = self.filter_frame(copy.deepcopy(self.frame_unfiltered))
                    cv.imshow('', frame_filtered)
                print(f"Filter set to {VideoFilter(self.video_filter).name.replace('_', ' ')}")

            # Press 'i' to print basic video information.
            elif wait_key_chr == 'i':
                self.print_basic_video_properties()

            elif wait_key_chr == 'o':
                video_file = filedialog.askopenfilename()
                name, ext = os.path.splitext(video_file)
                if ext in self.extensions:
                    self.video_file = video_file
                    user_request = True
                    break

            # Handle any other key press as setting/recalling a favorite video
            elif wait_key != 255:
                # print(f"Wait key code: {wait_key}")
                wait_key_chr = chr(wait_key)

                # Clear the favorites
                if wait_key_chr == 'x':
                    self.favorites_map.clear()
                    print(f"Clearing favorites.")
                elif wait_key in self.favorites_map.keys():
                    # Cue up the favorite video if we're not already playing it
                    if self.favorites_map[wait_key] != self.video_file:
                        self.video_file = self.favorites_map[wait_key]
                        user_request = True
                        print(f"Recalling favorite {wait_key_chr}")
                        break
                else:
                    already_mapped = False
                    for key in self.favorites_map.keys():
                        if self.video_file == self.favorites_map[key]:
                            print(f"This video already saved to key '{chr(key)}' (code: {key})")
                            already_mapped = True
                            break
                    if not already_mapped:
                        print(f"Saving video to favorite {wait_key_chr} (code: {wait_key})")
                        self.favorites_map[wait_key] = self.video_file

        self.video_capture.release()
        if self.with_audio:
            audio_capture.close_player()

        return user_request

    def play_videos(self, with_replacement=False):
        if len(self.video_files) == 0:
            print(f"Didn't find any video files. Load video files first.")
            return

        print(f"Found {len(self.video_files)} videos.")

        # If random with replacement, set up iterator to a pick random file from video files. Calling next() on this
        # iterator will always return a video file. If random without replacement, set up an empty iterator to be
        # initialized below, as it follows the same pattern as when we've exhausted the iterator.
        video_iterator = iter(lambda: random.choice(self.video_files), None) if with_replacement else iter([])

        while self.abort_key != 'q':
            try:
                # This will only fail if there's nothing left to iterate over, which is only in the without replacement
                # case. When we have run out of unique video files, as well as initially when we have an empty iterator,
                # this call to next() will raise a StopIteration exception.
                self.video_file = next(video_iterator)

                # Play the video. If the user requests a favorite video, that current video will get unloaded,
                # the player's video file will point to the favorite video, and play_video() will return True.
                # If play_video() returns False, we can move on to the next random video.
                user_request = self.play_video()
                while user_request:
                    user_request = self.play_video()

            except StopIteration:
                # The iterator is empty. Randomize the file order, re-initialize the iterator, and try againd.
                random.shuffle(self.video_files)
                video_iterator = iter(self.video_files)

def watch_camera():
    camera_capture = cv.VideoCapture(0)

    fps = camera_capture.get(cv.CAP_PROP_FPS)
    frame_time_ms = int(1000.0 / fps)
    print(f"{fps} fps = {frame_time_ms}ms/frame.")

    while True:
        ret, frame = camera_capture.read()
        if not ret:
            continue

        cv.imshow('', frame)

        wait_key = cv.waitKey(frame_time_ms) & 0xFF
        wait_key_chr = chr(wait_key)
        if wait_key_chr == 'q':
            break

def mix_video_with_camera(video_directory, extensions):
    camera_capture = cv.VideoCapture(0)
    camera_fps = camera_capture.get(cv.CAP_PROP_FPS)
    camera_frame_time_ms = int(1000.0 / camera_fps)
    camera_width, camera_height = camera_capture.get(cv.CAP_PROP_FRAME_WIDTH), camera_capture.get(cv.CAP_PROP_FRAME_HEIGHT)

    video_files = get_files(video_directory, extensions, recursive=False)
    random.shuffle(video_files)
    video_files_iter = iter(video_files)
    video_file = next(video_files_iter)
    video_capture = cv.VideoCapture(video_file)
    video_fps = video_capture.get(cv.CAP_PROP_FPS)
    video_frame_time_ms = int(1000.0 / video_fps)
    video_width, video_height = video_capture.get(cv.CAP_PROP_FRAME_WIDTH), video_capture.get(cv.CAP_PROP_FRAME_HEIGHT)

    while True:
        camera_ret, camera_frame = camera_capture.read()
        #cv.imshow('', camera_frame)

        wait_key = cv.waitKey(camera_frame_time_ms) & 0xFF
        if wait_key == ord('q'):
            break

        video_ret, video_frame = video_capture.read()
        if not video_ret:
            try:
                video_file = next(video_files_iter)
            except:
                random.shuffle(video_files)
                video_files_iter = iter(video_files)
                video_file = next(video_files_iter)

            video_capture.release()
            video_capture = cv.VideoCapture(video_file)
            video_fps = video_capture.get(cv.CAP_PROP_FPS)
            video_frame_time_ms = int(1000.0 / video_fps)
            video_ret, video_frame = video_capture.read()

        video_frame_shape = video_frame.shape
        print(video_frame_shape)
        camera_frame = np.zeros(video_frame_shape, np.uint8) + camera_frame

        cv.imshow('', camera_frame)

        wait_key = cv.waitKey(video_frame_time_ms) & 0xFF
        if wait_key == ord('q'):
            break










