import React, { useRef, useState, useEffect } from 'react';
import ReactPlayer from 'react-player';
import {
  Box,
  Typography,
  IconButton,
  Slider,
  Paper,
  Chip,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  VolumeUp,
  VolumeOff,
  Fullscreen,
} from '@mui/icons-material';

interface Video {
  id: string;
  name: string;
  url: string;
  s3Uri: string;
  status: 'uploading' | 'uploaded' | 'processing' | 'completed' | 'failed';
  analysisResults?: any;
}

interface Highlight {
  timestamp: number;
  type: string;
  description: string;
}

interface VideoPlayerProps {
  video: Video;
  onTimeUpdate?: (currentTime: number) => void;
  seekToTime?: number;
  highlights?: Highlight[];
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({
  video,
  onTimeUpdate,
  seekToTime,
  highlights = [],
}) => {
  const playerRef = useRef<ReactPlayer>(null);
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(0.8);
  const [muted, setMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [seeking, setSeeking] = useState(false);

  // Seek to specific time when requested
  useEffect(() => {
    if (seekToTime !== undefined && playerRef.current) {
      playerRef.current.seekTo(seekToTime, 'seconds');
    }
  }, [seekToTime]);

  const handlePlayPause = () => {
    setPlaying(!playing);
  };

  const handleVolumeChange = (event: Event | React.SyntheticEvent<Element, Event>, newValue: number | number[]) => {
    setVolume(newValue as number);
    setMuted(false);
  };

  const handleMute = () => {
    setMuted(!muted);
  };

  const handleSeekChange = (event: Event | React.SyntheticEvent<Element, Event>, newValue: number | number[]) => {
    setCurrentTime(newValue as number);
    setSeeking(true);
  };

  const handleSeekCommit = (event: Event | React.SyntheticEvent<Element, Event>, newValue: number | number[]) => {
    if (playerRef.current) {
      playerRef.current.seekTo(newValue as number, 'seconds');
    }
    setSeeking(false);
  };

  const handleProgress = (state: { played: number; playedSeconds: number; loaded: number; loadedSeconds: number }) => {
    if (!seeking) {
      setCurrentTime(state.playedSeconds);
      onTimeUpdate?.(state.playedSeconds);
    }
  };

  const handleDuration = (duration: number) => {
    setDuration(duration);
  };

  const handleFullscreen = () => {
    if (playerRef.current) {
      const playerElement = playerRef.current.getInternalPlayer() as HTMLVideoElement;
      if (playerElement.requestFullscreen) {
        playerElement.requestFullscreen();
      }
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'processing':
        return 'warning';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'uploaded':
        return 'Ready for Analysis';
      case 'processing':
        return 'Analyzing...';
      case 'completed':
        return 'Analysis Complete';
      case 'failed':
        return 'Analysis Failed';
      default:
        return status;
    }
  };

  return (
    <Paper elevation={2} sx={{ overflow: 'hidden' }}>
      {/* Video Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle2" noWrap sx={{ flexGrow: 1, mr: 2 }}>
            {video.name}
          </Typography>
          <Chip
            label={getStatusText(video.status)}
            color={getStatusColor(video.status) as any}
            size="small"
          />
        </Box>
      </Box>

      {/* Video Player */}
      <Box sx={{ position: 'relative', aspectRatio: '16/9', bgcolor: 'black' }}>
        <ReactPlayer
          ref={playerRef}
          url={video.url}
          width="100%"
          height="100%"
          playing={playing}
          volume={muted ? 0 : volume}
          onProgress={handleProgress}
          onDuration={handleDuration}
          controls={false}
          style={{ position: 'absolute', top: 0, left: 0 }}
        />
      </Box>

      {/* Custom Controls */}
      <Box sx={{ p: 2, bgcolor: 'grey.50' }}>
        {/* Progress Bar with Timeline Markers */}
        <Box sx={{ mb: 2, position: 'relative' }}>
          {/* Timeline Markers */}
          {highlights.length > 0 && duration > 0 && (
            <Box sx={{ position: 'absolute', top: -8, left: 0, right: 0, height: 4, zIndex: 1 }}>
              {highlights.map((highlight, index) => {
                const position = (highlight.timestamp / 1000 / duration) * 100;
                const getMarkerColor = (type: string) => {
                  if (type.includes('goal')) return '#ff9800'; // orange
                  if (type.includes('save')) return '#2196f3'; // blue
                  if (type.includes('fight') || type.includes('penalty')) return '#f44336'; // red
                  if (type.includes('player')) return '#4caf50'; // green
                  return '#9c27b0'; // purple
                };
                
                return (
                  <Box
                    key={index}
                    sx={{
                      position: 'absolute',
                      left: `${position}%`,
                      top: 0,
                      width: 3,
                      height: 16,
                      bgcolor: getMarkerColor(highlight.type),
                      borderRadius: '2px',
                      cursor: 'pointer',
                      transform: 'translateX(-50%)',
                      '&:hover': {
                        height: 20,
                        top: -2,
                        boxShadow: 2,
                      },
                    }}
                    title={`${highlight.description} - ${formatTime(highlight.timestamp / 1000)}`}
                    onClick={() => {
                      if (playerRef.current) {
                        playerRef.current.seekTo(highlight.timestamp / 1000, 'seconds');
                      }
                    }}
                  />
                );
              })}
            </Box>
          )}
          
          <Slider
            value={currentTime}
            max={duration}
            onChange={handleSeekChange}
            onChangeCommitted={handleSeekCommit}
            size="small"
            sx={{
              '& .MuiSlider-thumb': {
                width: 12,
                height: 12,
                zIndex: 2,
              },
              '& .MuiSlider-track': {
                height: 4,
              },
              '& .MuiSlider-rail': {
                height: 4,
              },
            }}
          />
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {formatTime(currentTime)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatTime(duration)}
            </Typography>
          </Box>
          
          {/* Highlight Legend */}
          {highlights.length > 0 && (
            <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
              <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                Timeline:
              </Typography>
              {Array.from(new Set(highlights.map(h => h.type))).map((type) => {
                const getMarkerColor = (type: string) => {
                  if (type.includes('goal')) return '#ff9800';
                  if (type.includes('save')) return '#2196f3';
                  if (type.includes('fight') || type.includes('penalty')) return '#f44336';
                  if (type.includes('player')) return '#4caf50';
                  return '#9c27b0';
                };
                
                return (
                  <Box key={type} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        bgcolor: getMarkerColor(type),
                        borderRadius: '50%',
                      }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {type}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* Control Buttons */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton onClick={handlePlayPause} size="small">
            {playing ? <Pause /> : <PlayArrow />}
          </IconButton>

          <IconButton onClick={handleMute} size="small">
            {muted ? <VolumeOff /> : <VolumeUp />}
          </IconButton>

          <Box sx={{ width: 80, mx: 1 }}>
            <Slider
              value={volume}
              onChange={handleVolumeChange}
              min={0}
              max={1}
              step={0.1}
              size="small"
            />
          </Box>

          <Box sx={{ flexGrow: 1 }} />

          <IconButton onClick={handleFullscreen} size="small">
            <Fullscreen />
          </IconButton>
        </Box>
      </Box>
    </Paper>
  );
};

export default VideoPlayer;
