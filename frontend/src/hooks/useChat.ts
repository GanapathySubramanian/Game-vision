import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { agentApi, ChatMessage, BedrockAgentResponse } from '../services/api';

export interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  sessionId: string | null;
  sendMessage: (message: string) => Promise<void>;
  startConversation: (videoId?: string) => Promise<void>;
  clearConversation: () => void;
  endConversation: () => Promise<void>;
}

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const currentVideoId = useRef<string | undefined>();

  const startConversation = useCallback(async (videoId?: string) => {
    try {
      setIsLoading(true);
      currentVideoId.current = videoId;
      
      const response = await agentApi.startConversation(videoId);
      setSessionId(response.sessionId);
      
      // Clear previous messages when starting a new conversation
      setMessages([]);
      
      // Add welcome message - only shown after analysis is complete
      const welcomeMessage: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: videoId 
          ? '✅ Analysis complete! I\'m ready to answer your questions about the video. Ask me about gameplay, players, key moments, highlights, or request a summary.'
          : 'Hello! Please upload a video to start the analysis.',
        timestamp: new Date(),
        videoId,
      };
      
      setMessages([welcomeMessage]);
    } catch (error) {
      console.error('Failed to start conversation:', error);
      // Add error message
      const errorMessage: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: 'Sorry, I encountered an error starting our conversation. Please try again.',
        timestamp: new Date(),
      };
      setMessages([errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (message: string) => {
    if (!sessionId || !message.trim()) {
      return;
    }

    const userMessage: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content: message.trim(),
      timestamp: new Date(),
      videoId: currentVideoId.current,
    };

    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response: BedrockAgentResponse = await agentApi.sendMessage(
        sessionId,
        message,
        currentVideoId.current
      );

      const assistantMessage: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: response.output.text,
        timestamp: new Date(),
        videoId: currentVideoId.current,
      };

      // Add assistant response
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      
      const errorMessage: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your message. Please try again.',
        timestamp: new Date(),
        videoId: currentVideoId.current,
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const clearConversation = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    currentVideoId.current = undefined;
  }, []);

  const endConversation = useCallback(async () => {
    if (sessionId) {
      try {
        await agentApi.endConversation(sessionId);
      } catch (error) {
        console.error('Failed to end conversation:', error);
      }
    }
    clearConversation();
  }, [sessionId, clearConversation]);

  return {
    messages,
    isLoading,
    sessionId,
    sendMessage,
    startConversation,
    clearConversation,
    endConversation,
  };
};
