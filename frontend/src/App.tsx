import React, { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  AppBar,
  Toolbar,
  IconButton,
  Alert,
} from '@mui/material';
import {
  Chat,
  Settings,
  Brightness4,
  Brightness7,
} from '@mui/icons-material';

import logo from './assets/images/logo.png';
import ChatInterface from './components/ChatInterface';
import VideoUpload from './components/VideoUpload';
import VideoPlayer from './components/VideoPlayer';
import AnalysisDisplay from './components/AnalysisDisplay';
import { useChat } from './hooks/useChat';
import { useVideoUpload } from './hooks/useVideoUpload';

interface Video {
  id: string;
  name: string;
  url: string;
  s3Uri: string;
  status: 'uploading' | 'uploaded' | 'processing' | 'completed' | 'failed';
  analysisResults?: any;
}

interface AnalysisResult {
  highlights: Array<{
    type: string;
    timestamp: number;
    endTimestamp?: number;
    description: string;
    timecode: string;
    playerName?: string;
    confidence?: number;
  }>;
  gameStats: {
    totalGoals: number;
    totalPenalties: number;
    keyPlayers: string[];
    totalDuration: number;
    highlightsCount: number;
  };
  scenes: Array<{
    type: string;
    startTime: number;
    endTime: number;
    description: string;
  }>;
  gameContext?: {
    location: string;
    atmosphere: string;
    advertisements: string[];
  };
  crowdReactions?: Array<{
    type: string;
    timestamp: number;
    endTimestamp?: number;
    description: string;
    timecode: string;
  }>;
  chapters?: Array<{
    index: number;
    startTime: number;
    endTime: number;
    duration: number;
    timecode: string;
    summary: string;
  }>;
  analysisConfidence?: number;
  analysisTimestamp: string;
}

function App() {
  const [darkMode, setDarkMode] = useState(false);
  const [currentVideo, setCurrentVideo] = useState<Video | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<'ready' | 'analyzing' | 'complete' | 'error'>('ready');
  const [seekToTime, setSeekToTime] = useState<number | undefined>(undefined);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const {
    messages,
    isLoading,
    sendMessage,
    startConversation,
    clearConversation,
  } = useChat();

  const {
    uploadVideo,
    uploadProgress,
    isUploading,
  } = useVideoUpload();

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: '#1976d2',
      },
      secondary: {
        main: '#dc004e',
      },
    },
    typography: {
      h4: {
        fontWeight: 600,
      },
      h6: {
        fontWeight: 500,
      },
    },
  });

  const handleVideoUpload = async (file: File) => {
    try {
      setUploadError(null);
      const result = await uploadVideo(file);
      
      const newVideo: Video = {
        id: result.videoId,
        name: file.name,
        url: URL.createObjectURL(file),
        s3Uri: result.s3Uri,
        status: 'uploaded',
      };

      setVideos(prev => [...prev, newVideo]);
      setCurrentVideo(newVideo);
      setAnalysisStatus('ready');
      setAnalysisResult(null);

      // Clear any previous conversation - chat will start after analysis completes
      clearConversation();
      
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
    }
  };

  // Transform raw BDA data to frontend format
  const transformBDAResults = (rawBDA: any): AnalysisResult => {
    const chapters = rawBDA.chapters || [];
    const inferenceResult = rawBDA.inference_result || {};
    const matchedBlueprint = rawBDA.matched_blueprint || {};
    
    const highlights: any[] = [];
    const crowdReactions: any[] = [];
    const scenes: any[] = [];
    const keyPlayers = new Set<string>();
    let totalGoals = 0;
    let totalPenalties = 0;
    let maxTimestamp = 0;
    
    // Process each chapter
    chapters.forEach((chapter: any) => {
      const chapterInference = chapter.inference_result || {};
      const startTime = (chapter.start_timestamp_millis || 0) / 1000;
      const endTime = (chapter.end_timestamp_millis || 0) / 1000;
      const timecode = chapter.start_timecode_smpte || '00:00:00;00';
      
      maxTimestamp = Math.max(maxTimestamp, endTime);
      
      // Extract player actions
      const playerActions = chapterInference.player_actions || {};
      if (playerActions.action_type && playerActions.description && 
          playerActions.description !== 'Not applicable' && playerActions.description !== '') {
        highlights.push({
          type: `player_${playerActions.action_type}`,
          timestamp: startTime * 1000,
          endTimestamp: endTime * 1000,
          description: playerActions.description,
          timecode: timecode,
          playerName: playerActions.player_name || '',
          confidence: 0.9
        });
        
        if (playerActions.action_type.toLowerCase() === 'goal') {
          totalGoals++;
        }
        
        if (playerActions.player_name) {
          keyPlayers.add(playerActions.player_name);
        }
      }
      
      // Extract game events
      const gameEvents = chapterInference.game_events || {};
      if (gameEvents.event_type && gameEvents.description && 
          gameEvents.description !== 'Not applicable' && gameEvents.description !== '') {
        highlights.push({
          type: `game_${gameEvents.event_type}`,
          timestamp: startTime * 1000,
          endTimestamp: endTime * 1000,
          description: gameEvents.description,
          timecode: timecode,
          confidence: 0.9
        });
        
        if (gameEvents.event_type.toLowerCase() === 'goal') {
          totalGoals++;
        }
      }
      
      // Extract spectator reactions
      const spectatorReactions = chapterInference.spectator_reactions || {};
      if (spectatorReactions.reaction_type && spectatorReactions.description && 
          spectatorReactions.description !== 'Not applicable' && spectatorReactions.description !== '') {
        crowdReactions.push({
          type: spectatorReactions.reaction_type,
          timestamp: startTime * 1000,
          endTimestamp: endTime * 1000,
          description: spectatorReactions.description,
          timecode: timecode
        });
        
        highlights.push({
          type: `crowd_${spectatorReactions.reaction_type}`,
          timestamp: startTime * 1000,
          endTimestamp: endTime * 1000,
          description: spectatorReactions.description,
          timecode: timecode,
          confidence: 0.8
        });
      }
      
      // Extract locker room scenes
      const lockerScenes = chapterInference.locker_room_scenes || {};
      if (lockerScenes.scene_type && lockerScenes.description && 
          lockerScenes.description !== 'Not applicable' && lockerScenes.description !== '') {
        scenes.push({
          type: `locker_${lockerScenes.scene_type}`,
          startTime: startTime,
          endTime: endTime,
          description: lockerScenes.description
        });
        
        highlights.push({
          type: `scene_locker_${lockerScenes.scene_type}`,
          timestamp: startTime * 1000,
          endTimestamp: endTime * 1000,
          description: lockerScenes.description,
          timecode: timecode,
          confidence: 0.85
        });
      }
      
      // Extract team bus scenes
      const busScenes = chapterInference.team_bus_scenes || {};
      if (busScenes.scene_type && busScenes.description && 
          busScenes.description !== 'Not applicable' && busScenes.description !== '') {
        scenes.push({
          type: `bus_${busScenes.scene_type}`,
          startTime: startTime,
          endTime: endTime,
          description: busScenes.description
        });
        
        highlights.push({
          type: `scene_bus_${busScenes.scene_type}`,
          timestamp: startTime * 1000,
          endTimestamp: endTime * 1000,
          description: busScenes.description,
          timecode: timecode,
          confidence: 0.85
        });
      }
    });
    
    // Sort highlights by timestamp
    highlights.sort((a, b) => a.timestamp - b.timestamp);
    crowdReactions.sort((a, b) => a.timestamp - b.timestamp);
    
    // Parse advertisements
    const adsString = inferenceResult.advertisements || '';
    const advertisements = adsString ? adsString.split(',').map((ad: string) => ad.trim()) : [];
    
    return {
      highlights,
      gameStats: {
        totalGoals,
        totalPenalties,
        keyPlayers: Array.from(keyPlayers),
        totalDuration: maxTimestamp,
        highlightsCount: highlights.length
      },
      scenes,
      gameContext: {
        location: inferenceResult.game_location || '',
        atmosphere: inferenceResult.game_atmosphere || '',
        advertisements
      },
      crowdReactions,
      chapters: chapters.map((ch: any, idx: number) => ({
        index: ch.chapter_index !== undefined ? ch.chapter_index : idx,
        startTime: (ch.start_timestamp_millis || 0) / 1000,
        endTime: (ch.end_timestamp_millis || 0) / 1000,
        duration: (ch.duration_millis || 0) / 1000,
        timecode: ch.start_timecode_smpte || '00:00:00;00',
        summary: `Chapter ${(ch.chapter_index !== undefined ? ch.chapter_index : idx) + 1}`
      })),
      analysisConfidence: matchedBlueprint.confidence || 1.0,
      analysisTimestamp: new Date().toISOString()
    };
  };

  const handleVideoAnalysis = async (videoId: string) => {
    try {
      setAnalysisStatus('analyzing');
      setAnalysisResult(null);
      
      // Call backend API and wait for results (synchronous)
      const response = await fetch(`/api/analyze-video/${videoId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      console.log(response);
      
      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Analysis completed:', result);
      
      // Check if analysis completed successfully
      if (result.status === 'completed' && result.results) {
        
        // Transform raw BDA data to frontend format
        const validatedResults: AnalysisResult = transformBDAResults(result.results);

        console.log('Transformed analysis results:', validatedResults);
        
        // Set results immediately - no polling needed!
        setAnalysisResult(validatedResults);
        setAnalysisStatus('complete');

        // Update current video status
        if (currentVideo) {
          const updatedVideo = { 
            ...currentVideo, 
            status: 'completed' as const, 
            analysisResults: validatedResults 
          };
          setCurrentVideo(updatedVideo);
          setVideos(prev => prev.map(v => v.id === videoId ? updatedVideo : v));
        }

        // NOW start the chat conversation - analysis is complete and data is available
        await startConversation(videoId);
        console.log('Chat conversation started after analysis completion');
      } else {
        // Analysis failed or returned unexpected status
        throw new Error(result.message || 'Analysis returned unexpected status');
      }

    } catch (error) {
      console.error('Analysis failed:', error);
      setAnalysisStatus('error');
      setUploadError(error instanceof Error ? error.message : 'Analysis failed');
    }
  };

  const pollAnalysisResults = async (videoId: string) => {
    const maxAttempts = 60; // Poll for up to 10 minutes (60 * 10 seconds)
    let attempts = 0;

    const poll = async () => {
      try {
        attempts++;
        
        const response = await fetch(`/api/analysis-status/${videoId}`);
        if (!response.ok) {
          throw new Error('Failed to get analysis status');
        }

        const statusResult = await response.json();
        
        if (statusResult.status === 'completed' && statusResult.results) {
          // Analysis complete, set results
          setAnalysisResult(statusResult.results);
          setAnalysisStatus('complete');

          // Update current video status
          if (currentVideo) {
            const updatedVideo = { ...currentVideo, status: 'completed' as const, analysisResults: statusResult.results };
            setCurrentVideo(updatedVideo);
            setVideos(prev => prev.map(v => v.id === videoId ? updatedVideo : v));
          }
          
          return;
        } else if (statusResult.status === 'processing') {
          // Still processing, continue polling
          if (attempts < maxAttempts) {
            setTimeout(poll, 10000); // Poll every 10 seconds
          } else {
            // Timeout
            setAnalysisStatus('error');
            console.error('Analysis timeout');
          }
        } else {
          // Error or unknown status
          setAnalysisStatus('error');
          console.error('Analysis failed:', statusResult);
        }
      } catch (error) {
        console.error('Polling error:', error);
        if (attempts < maxAttempts) {
          setTimeout(poll, 10000); // Retry after 10 seconds
        } else {
          setAnalysisStatus('error');
        }
      }
    };

    // Start polling
    poll();
  };

  const handleSeekToTime = (timeInSeconds: number) => {
    setSeekToTime(timeInSeconds);
    // Reset after a short delay to allow for multiple seeks
    setTimeout(() => setSeekToTime(undefined), 100);
  };

  const handleSendMessage = async (message: string) => {
    if (!currentVideo) {
      return;
    }
    
    await sendMessage(message);
  };

  const clearUploadError = () => {
    setUploadError(null);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ flexGrow: 1, minHeight: '100vh', bgcolor: 'background.default' }}>
        <AppBar position="static" elevation={1}>
          <Toolbar>
            <img src={logo} alt="GameVision Logo" style={{ height: '70px', marginRight: '-10px' }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              GameVision
            </Typography>
            <IconButton
              color="inherit"
              onClick={() => setDarkMode(!darkMode)}
              sx={{ mr: 1 }}
            >
              {darkMode ? <Brightness7 /> : <Brightness4 />}
            </IconButton>
          </Toolbar>
        </AppBar>

        <Container maxWidth="xl" sx={{ mt: 1, mb: 1, height: 'calc(100vh - 64px)' }}>
          <Grid container spacing={2} sx={{ height: '100%' }}>
            {/* Left Panel - Video Upload and Player */}
            <Grid item xs={12} md={3.5} sx={{ height: '100%' }}>
              <Paper
                elevation={2}
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
              >
                <Box sx={{ p: 2, pb: 1, flexShrink: 0 }}>
                  <Typography variant="h6" gutterBottom sx={{ mb: 0 }}>
                    Video Upload & Player
                  </Typography>
                </Box>

                <Box sx={{ 
                  flex: 1, 
                  overflow: 'auto',
                  px: 2,
                  pb: 2,
                  display: 'flex',
                  flexDirection: 'column',
                  '&::-webkit-scrollbar': {
                    width: '6px',
                  },
                  '&::-webkit-scrollbar-track': {
                    background: 'transparent',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    background: '#bbb',
                    borderRadius: '3px',
                  },
                  '&::-webkit-scrollbar-thumb:hover': {
                    background: '#999',
                  },
                }}>
                  <Box sx={{ mb: 2, flexShrink: 0 }}>
                    <VideoUpload
                      onUpload={handleVideoUpload}
                      onAnalyze={handleVideoAnalysis}
                      isUploading={isUploading}
                      uploadProgress={uploadProgress}
                      error={uploadError}
                      onClearError={clearUploadError}
                      uploadedVideo={currentVideo ? {
                        videoId: currentVideo.id,
                        fileName: currentVideo.name,
                        s3Uri: currentVideo.s3Uri,
                      } : null}
                      analysisStatus={analysisStatus}
                    />
                  </Box>

                  {currentVideo && (
                    <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                      <VideoPlayer
                        video={currentVideo}
                        onTimeUpdate={(time) => {
                          // Handle time updates for timestamp-based queries
                        }}
                        seekToTime={seekToTime}
                        highlights={analysisResult?.highlights || []}
                      />
                    </Box>
                  )}

                  {!currentVideo && (
                    <Box
                      sx={{
                        flexGrow: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'text.secondary',
                      }}
                    >
                      <Typography variant="body2" align="center">
                        Upload a video to start analysis
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Paper>
            </Grid>

            {/* Center Panel - Analysis Results */}
            <Grid item xs={12} md={4.5} sx={{ height: '100%' }}>
              <AnalysisDisplay
                analysisResult={analysisResult}
                onSeekToTime={handleSeekToTime}
                isLoading={analysisStatus === 'analyzing'}
              />
            </Grid>

            {/* Right Panel - Chat Interface */}
            <Grid item xs={12} md={4} sx={{ height: '100%' }}>
              <Paper
                elevation={2}
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
              >
                <Box
                  sx={{
                    p: 2,
                    borderBottom: 1,
                    borderColor: 'divider',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <Chat sx={{ mr: 1 }} />
                  <Typography variant="h6">
                    Chat with AI Agent
                  </Typography>
                  {currentVideo && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ ml: 'auto' }}
                    >
                      Analyzing: {currentVideo.name}
                    </Typography>
                  )}
                </Box>

                <ChatInterface
                  messages={messages}
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading}
                  disabled={!currentVideo || analysisStatus !== 'complete' || messages.length === 0}
                  placeholder={
                    !currentVideo
                      ? "Upload a video to start chatting"
                      : analysisStatus === 'analyzing'
                      ? "Analyzing video... Please wait"
                      : analysisStatus === 'complete' && messages.length === 0
                      ? "Starting chat..."
                      : analysisStatus === 'complete'
                      ? "Ask me anything about the video..."
                      : "Click 'Analyze' to process the video"
                  }
                />
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
