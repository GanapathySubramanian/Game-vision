import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Button,
  Card,
  CardContent,
  Grid,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  SportsHockey,
  Timer,
  Person,
  EmojiEvents,
  Security,
  Warning,
  AccessTime,
  PlayArrow,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';

interface Highlight {
  type: string;
  timestamp: number;
  endTimestamp?: number;
  description: string;
  timecode: string;
  playerName?: string;
  confidence?: number;
}

interface GameStats {
  totalGoals: number;
  totalPenalties: number;
  keyPlayers: string[];
  totalDuration: number;
  highlightsCount: number;
}

interface AnalysisResult {
  highlights: Highlight[];
  gameStats: GameStats;
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

interface AnalysisDisplayProps {
  analysisResult: AnalysisResult | null;
  onSeekToTime?: (timeInSeconds: number) => void;
  isLoading?: boolean;
}

const AnalysisDisplay: React.FC<AnalysisDisplayProps> = ({
  analysisResult,
  onSeekToTime,
  isLoading = false,
}) => {
  const [showAllChapters, setShowAllChapters] = useState(false);
  const [showAllHighlights, setShowAllHighlights] = useState(false);
  const [expandedAtmosphere, setExpandedAtmosphere] = useState(false);
  const [expandedScenes, setExpandedScenes] = useState<{[key: number]: boolean}>({});
  
  const formatTime = (milliseconds: number): string => {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const getHighlightIcon = (type: string) => {
    if (type.includes('goal')) return <EmojiEvents sx={{ color: 'gold' }} />;
    if (type.includes('save')) return <Security sx={{ color: 'blue' }} />;
    if (type.includes('fight') || type.includes('penalty')) return <Warning sx={{ color: 'red' }} />;
    if (type.includes('player')) return <Person sx={{ color: 'green' }} />;
    return <SportsHockey sx={{ color: 'primary.main' }} />;
  };

  const getHighlightColor = (type: string) => {
    if (type.includes('goal')) return 'warning';
    if (type.includes('save')) return 'info';
    if (type.includes('fight') || type.includes('penalty')) return 'error';
    if (type.includes('player')) return 'success';
    return 'primary';
  };

  const handleTimeClick = (timestamp: number) => {
    if (onSeekToTime) {
      const timeInSeconds = Math.floor(timestamp / 1000);
      onSeekToTime(timeInSeconds);
    }
  };

  if (isLoading) {
    return (
      <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
        <Typography variant="h6" gutterBottom>
          Analysis Results
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            Processing video analysis...
          </Typography>
        </Box>
      </Paper>
    );
  }

  if (!analysisResult) {
    return (
      <Paper elevation={2} sx={{ p: 3, height: '100%' }}>
        <Typography variant="h6" gutterBottom>
          Analysis Results
        </Typography>
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body1" color="text.secondary">
            Upload and analyze a video to see results here
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper 
      elevation={2} 
      sx={{ 
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}
    >
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 1, 
        p: 2,
        pb: 1,
        flexShrink: 0 
      }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Analysis Results
        </Typography>
        <Chip 
          label={`${analysisResult?.highlights?.length || 0}`} 
          size="small" 
          color="primary"
          sx={{ fontWeight: 600 }}
        />
      </Box>

      <Box sx={{ 
        flex: 1, 
        overflow: 'auto',
        px: 2,
        pb: 2,
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
        {/* Game Context Accordion */}
        {analysisResult.gameContext && (
          <Accordion 
            defaultExpanded 
            sx={{ 
              mb: 2,
              boxShadow: 1,
              '&:before': { display: 'none' }
            }}
          >
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>
                  🏟️ Game Context
                </Typography>
                {analysisResult.analysisConfidence && (
                  <Chip 
                    label={`${Math.round(analysisResult.analysisConfidence * 100)}%`} 
                    size="small" 
                    color="success"
                    sx={{ ml: 'auto', height: 20, fontSize: '0.7rem' }}
                  />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              {analysisResult.gameContext.location && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block', mb: 0.3 }}>
                    📍 Location
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                    {analysisResult.gameContext.location}
                  </Typography>
                </Box>
              )}
              
              {analysisResult.gameContext.atmosphere && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block', mb: 0.3 }}>
                    ⚡ Atmosphere
                  </Typography>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontSize: '0.85rem',
                      lineHeight: 1.4,
                      display: '-webkit-box',
                      WebkitLineClamp: expandedAtmosphere ? 'unset' : 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}
                  >
                    {analysisResult.gameContext.atmosphere}
                  </Typography>
                  {analysisResult.gameContext.atmosphere.length > 100 && (
                    <Button 
                      size="small" 
                      onClick={() => setExpandedAtmosphere(!expandedAtmosphere)}
                      sx={{ mt: 0.5, p: 0, minWidth: 'auto', fontSize: '0.75rem' }}
                    >
                      {expandedAtmosphere ? 'Show less' : 'Read more'}
                    </Button>
                  )}
                </Box>
              )}
              
              {analysisResult.gameContext.advertisements && analysisResult.gameContext.advertisements.length > 0 && (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}>
                    📺 Advertisements
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {analysisResult.gameContext.advertisements.map((ad, index) => (
                      <Chip 
                        key={index} 
                        label={ad} 
                        size="small" 
                        variant="outlined"
                        sx={{ height: 22, fontSize: '0.7rem' }}
                      />
                    ))}
                  </Box>
                </Box>
              )}
            </AccordionDetails>
          </Accordion>
        )}

        {/* Chapters Accordion */}
        {/* {analysisResult.chapters && analysisResult.chapters.length > 0 && (
          <Accordion 
            defaultExpanded
            sx={{ 
              mb: 2,
              boxShadow: 1,
              '&:before': { display: 'none' }
            }}
          >
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>
                📑 Chapters ({analysisResult.chapters.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0, pb: 1 }}>
              <List dense disablePadding>
                {analysisResult.chapters.slice(0, showAllChapters ? undefined : 4).map((chapter) => (
                  <ListItem
                    key={chapter.index}
                    sx={{
                      border: 1,
                      borderColor: 'divider',
                      borderRadius: 1,
                      mb: 0.75,
                      p: 1,
                      cursor: onSeekToTime ? 'pointer' : 'default',
                      '&:hover': onSeekToTime ? {
                        bgcolor: 'action.hover',
                        borderColor: 'primary.main',
                      } : {},
                    }}
                    onClick={() => handleTimeClick(chapter.startTime * 1000)}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      <Chip 
                        label={chapter.index + 1} 
                        size="small" 
                        color="primary"
                        sx={{ width: 28, height: 28, fontSize: '0.75rem' }}
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="body2" sx={{ fontSize: '0.85rem', fontWeight: 500 }}>
                          {chapter.summary}
                        </Typography>
                      }
                      secondary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.3 }}>
                          <Button
                            size="small"
                            startIcon={<PlayArrow sx={{ fontSize: 14 }} />}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTimeClick(chapter.startTime * 1000);
                            }}
                            sx={{ minWidth: 'auto', px: 0.5, py: 0, fontSize: '0.7rem' }}
                          >
                            {chapter.timecode}
                          </Button>
                          <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                            • {Math.round(chapter.duration)}s
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
              {analysisResult.chapters.length > 4 && (
                <Button 
                  size="small" 
                  onClick={() => setShowAllChapters(!showAllChapters)}
                  sx={{ mt: 1, fontSize: '0.75rem' }}
                  endIcon={showAllChapters ? <ExpandLess /> : <ExpandMore />}
                >
                  {showAllChapters ? 'Show Less' : `Show All ${analysisResult.chapters.length} Chapters`}
                </Button>
              )}
            </AccordionDetails>
          </Accordion>
        )} */}

        {/* Game Statistics */}
        {/* <Accordion 
          defaultExpanded
          sx={{ 
            mb: 2,
            boxShadow: 1,
            '&:before': { display: 'none' }
          }}
        >
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>
              📈 Game Statistics
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center', p: 1, bgcolor: 'warning.50', borderRadius: 1 }}>
                  <Typography variant="h5" color="warning.main" sx={{ fontWeight: 700 }}>
                    {analysisResult.gameStats.totalGoals}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                    Goals
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center', p: 1, bgcolor: 'error.50', borderRadius: 1 }}>
                  <Typography variant="h5" color="error.main" sx={{ fontWeight: 700 }}>
                    {analysisResult.gameStats.totalPenalties}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                    Penalties
                  </Typography>
                </Box>
              </Grid>
            </Grid>
            
            {analysisResult.gameStats.keyPlayers.length > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}>
                  Key Players
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {analysisResult.gameStats.keyPlayers.map((player, index) => (
                    <Chip 
                      key={index} 
                      label={player} 
                      size="small" 
                      variant="outlined"
                      sx={{ height: 22, fontSize: '0.7rem' }}
                    />
                  ))}
                </Box>
              </Box>
            )}
          </AccordionDetails>
        </Accordion> */}

      {/* Key Highlights */}
      {analysisResult.highlights && analysisResult.highlights.length > 0 && (
        <Accordion 
          defaultExpanded
          sx={{ 
            mb: 2,
            boxShadow: 1,
            '&:before': { display: 'none' }
          }}
        >
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>
              🎯 Key Highlights
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, pb: 1 }}>
            <List dense disablePadding>
              {analysisResult.highlights.slice(0, showAllHighlights ? undefined : 5).map((highlight, index) => (
                <ListItem
                  key={index}
                  sx={{
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                    mb: 0.75,
                    p: 1,
                    cursor: onSeekToTime ? 'pointer' : 'default',
                    '&:hover': onSeekToTime ? {
                      bgcolor: 'action.hover',
                      borderColor: 'primary.main',
                    } : {},
                  }}
                  onClick={() => handleTimeClick(highlight.timestamp)}
                >
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    {getHighlightIcon(highlight.type)}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5, flexWrap: 'wrap' }}>
                        <Typography 
                          variant="body2" 
                          sx={{ 
                            fontSize: '0.8rem',
                            lineHeight: 1.3,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            flex: 1
                          }}
                        >
                          {highlight.description}
                        </Typography>
                        {highlight.playerName && (
                          <Chip 
                            label={highlight.playerName} 
                            size="small" 
                            color={getHighlightColor(highlight.type) as any}
                            variant="outlined"
                            sx={{ height: 18, fontSize: '0.65rem' }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.3 }}>
                        <Button
                          size="small"
                          startIcon={<PlayArrow sx={{ fontSize: 12 }} />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTimeClick(highlight.timestamp);
                          }}
                          sx={{ minWidth: 'auto', px: 0.5, py: 0, fontSize: '0.65rem' }}
                        >
                          {highlight.timecode}
                        </Button>
                        <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>
                          ({formatTime(highlight.timestamp)})
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
            {analysisResult.highlights.length > 5 && (
              <Button 
                size="small" 
                onClick={() => setShowAllHighlights(!showAllHighlights)}
                sx={{ mt: 1, fontSize: '0.75rem' }}
                endIcon={showAllHighlights ? <ExpandLess /> : <ExpandMore />}
              >
                {showAllHighlights ? 'Show Less' : `Show All ${analysisResult.highlights.length} Highlights`}
              </Button>
            )}
          </AccordionDetails>
        </Accordion>
      )}

      {/* Crowd Reactions (NEW) */}
      {analysisResult.crowdReactions && analysisResult.crowdReactions.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
            👥 Crowd Reactions ({analysisResult.crowdReactions.length})
          </Typography>
          <List dense>
            {analysisResult.crowdReactions.slice(0, 5).map((reaction, index) => (
              <ListItem
                key={index}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1,
                  cursor: onSeekToTime ? 'pointer' : 'default',
                  '&:hover': onSeekToTime ? {
                    bgcolor: 'action.hover',
                    borderColor: 'primary.main',
                  } : {},
                }}
                onClick={() => handleTimeClick(reaction.timestamp * 1000)}
              >
                <ListItemIcon>
                  <Typography sx={{ fontSize: 24 }}>
                    {reaction.type === 'cheering' ? '🎉' : 
                     reaction.type === 'sitting' ? '🪑' : '👏'}
                  </Typography>
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {reaction.type.charAt(0).toUpperCase() + reaction.type.slice(1)}
                    </Typography>
                  }
                  secondary={
                    <>
                      <Typography variant="caption" display="block" sx={{ mb: 0.5 }}>
                        {reaction.description.length > 100 
                          ? `${reaction.description.substring(0, 100)}...` 
                          : reaction.description}
                      </Typography>
                      <Button
                        size="small"
                        startIcon={<PlayArrow />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleTimeClick(reaction.timestamp * 1000);
                        }}
                        sx={{ minWidth: 'auto', px: 1 }}
                      >
                        {reaction.timecode}
                      </Button>
                    </>
                  }
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      {/* Scene Analysis */}
      {analysisResult.scenes && analysisResult.scenes.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
            🎬 Scene Analysis ({analysisResult.scenes.length})
          </Typography>
          <List dense>
            {analysisResult.scenes.map((scene, index) => (
              <ListItem
                key={index}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1,
                  p: 1.5,
                  display: 'block',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1 }}>
                  <AccessTime sx={{ fontSize: 20, color: 'text.secondary', mt: 0.3 }} />
                  <Box sx={{ flex: 1 }}>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        fontSize: '0.85rem',
                        lineHeight: 1.4,
                        display: '-webkit-box',
                        WebkitLineClamp: expandedScenes[index] ? 'unset' : 3,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        mb: scene.description.length > 150 ? 0.5 : 0
                      }}
                    >
                      {scene.description}
                    </Typography>
                    {scene.description.length > 150 && (
                      <Button 
                        size="small" 
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedScenes(prev => ({...prev, [index]: !prev[index]}));
                        }}
                        sx={{ mt: 0.5, p: 0, minWidth: 'auto', fontSize: '0.75rem' }}
                      >
                        {expandedScenes[index] ? 'Show less' : 'Read more'}
                      </Button>
                    )}
                  </Box>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 4 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<PlayArrow />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTimeClick(scene.startTime * 1000);
                    }}
                    sx={{ 
                      minWidth: 'auto', 
                      px: 1.5, 
                      py: 0.5,
                      fontSize: '0.75rem',
                      fontWeight: 600
                    }}
                  >
                    Play {formatTime(scene.startTime * 1000)}
                  </Button>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                    to {formatTime(scene.endTime * 1000)}
                  </Typography>
                </Box>
              </ListItem>
            ))}
          </List>
        </Box>
      )}

        <Box sx={{ mt: 2, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
            Analysis completed: {new Date(analysisResult.analysisTimestamp).toLocaleString()}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};

export default AnalysisDisplay;
