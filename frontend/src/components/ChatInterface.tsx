import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  TextField,
  IconButton,
  List,
  ListItem,
  Paper,
  Typography,
  Avatar,
  Chip,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  Send,
  Person,
  SmartToy,
  AccessTime,
  Group,
} from '@mui/icons-material';
import { ChatMessage } from '../services/api';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => Promise<void>;
  isLoading: boolean;
  disabled?: boolean;
  placeholder?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  onSendMessage,
  isLoading,
  disabled = false,
  placeholder = "Type your message...",
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when not disabled
  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading || disabled) {
      return;
    }

    const message = inputMessage.trim();
    setInputMessage('');

    try {
      await onSendMessage(message);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Re-populate input on error
      setInputMessage(message);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const renderMessage = (message: ChatMessage) => {
    const isUser = message.role === 'user';
    
    return (
      <ListItem
        key={message.id}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
          px: 1,
          py: 0.5,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            maxWidth: '80%',
            flexDirection: isUser ? 'row-reverse' : 'row',
          }}
        >
          <Avatar
            sx={{
              width: 32,
              height: 32,
              mx: 1,
              bgcolor: isUser ? 'primary.main' : 'secondary.main',
            }}
          >
            {isUser ? <Person /> : <SmartToy />}
          </Avatar>
          
          <Paper
            elevation={1}
            sx={{
              p: 1.5,
              bgcolor: isUser ? 'primary.light' : (theme) => theme.palette.mode === 'dark' ? 'grey.800' : 'grey.100',
              color: 'text.primary',
              borderRadius: 2,
              maxWidth: '100%',
            }}
          >
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {message.content}
            </Typography>
            
            {/* Timestamp and metadata */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                mt: 1,
                opacity: 0.7,
              }}
            >
              <Typography variant="caption">
                {formatTimestamp(message.timestamp)}
              </Typography>
            </Box>

            {/* Related players chips */}
            {message.relatedPlayers && message.relatedPlayers.length > 0 && (
              <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                <Group sx={{ fontSize: 14, mr: 0.5, opacity: 0.7 }} />
                {message.relatedPlayers.map((player, index) => (
                  <Chip
                    key={index}
                    label={player}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: '0.7rem', height: 20 }}
                  />
                ))}
              </Box>
            )}

            {/* Relevant timestamps */}
            {message.relevantTimestamps && message.relevantTimestamps.length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                  <AccessTime sx={{ fontSize: 12, mr: 0.5 }} />
                  Key Moments:
                </Typography>
                {message.relevantTimestamps.slice(0, 3).map((ts, index) => (
                  <Box key={index} sx={{ ml: 2, mb: 0.5 }}>
                    <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                      {ts.timestamp}: {ts.description}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Box>
      </ListItem>
    );
  };

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Messages Area */}
      <Box
        sx={{
          flexGrow: 1,
          overflow: 'auto',
          px: 1,
          py: 1,
        }}
      >
        <List sx={{ py: 0 }}>
          {messages.map(renderMessage)}
          
          {/* Loading indicator */}
          {isLoading && (
            <ListItem
              sx={{
                display: 'flex',
                justifyContent: 'flex-start',
                px: 1,
                py: 0.5,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', ml: 5 }}>
                <CircularProgress size={16} sx={{ mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  AI is thinking...
                </Typography>
              </Box>
            </ListItem>
          )}
        </List>
        <div ref={messagesEndRef} />
      </Box>

      <Divider />

      {/* Input Area */}
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'flex-end',
          gap: 1,
        }}
      >
        <TextField
          ref={inputRef}
          fullWidth
          multiline
          maxRows={4}
          variant="outlined"
          placeholder={placeholder}
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled || isLoading}
          size="small"
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: 2,
            },
          }}
        />
        <IconButton
          color="primary"
          onClick={handleSendMessage}
          disabled={!inputMessage.trim() || isLoading || disabled}
          sx={{
            bgcolor: 'primary.main',
            color: 'white',
            '&:hover': {
              bgcolor: 'primary.dark',
            },
            '&:disabled': {
              bgcolor: 'grey.300',
              color: 'grey.500',
            },
          }}
        >
          <Send />
        </IconButton>
      </Box>
    </Box>
  );
};

export default ChatInterface;
