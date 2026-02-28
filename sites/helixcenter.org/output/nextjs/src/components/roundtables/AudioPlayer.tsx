"use client";

import { useRef, useState, useEffect } from "react";

interface AudioPlayerProps {
  src: string;
  duration?: string;
  title: string;
}

export function AudioPlayer({ src, duration, title }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onDurationChange = () => setTotalDuration(audio.duration);
    const onEnded = () => setPlaying(false);

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("durationchange", onDurationChange);
    audio.addEventListener("ended", onEnded);

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("durationchange", onDurationChange);
      audio.removeEventListener("ended", onEnded);
    };
  }, []);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
    } else {
      audio.play();
    }
    setPlaying(!playing);
  }

  function seek(e: React.ChangeEvent<HTMLInputElement>) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Number(e.target.value);
  }

  function formatTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  return (
    <div className="bg-gray-50 rounded-lg p-4 my-6">
      <audio ref={audioRef} src={src} preload="metadata" />

      <div className="flex items-center gap-4">
        {/* Play/Pause */}
        <button
          onClick={togglePlay}
          className="w-12 h-12 flex items-center justify-center bg-helix-blue text-white rounded-full hover:bg-helix-accent transition-colors flex-shrink-0"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
            </svg>
          ) : (
            <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>

        {/* Progress */}
        <div className="flex-1">
          <input
            type="range"
            min={0}
            max={totalDuration || 0}
            value={currentTime}
            onChange={seek}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-helix-blue"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>{formatTime(currentTime)}</span>
            <span>{duration || formatTime(totalDuration)}</span>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-500 mt-2">
        Listen to "{title}"
      </p>
    </div>
  );
}
