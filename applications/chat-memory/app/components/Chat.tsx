'use client';

import { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { marked } from 'marked';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [userId, setUserId] = useState<string>('');
  const [userName, setUserName] = useState<string>('');
  const [isClient, setIsClient] = useState(false);
  const [showUserSetup, setShowUserSetup] = useState(false);

  useEffect(() => {
    setIsClient(true);

    // Check if user has a stored identity
    const storedUserName = localStorage.getItem('chat-user-name');
    const storedUserId = localStorage.getItem('chat-user-id');

    if (storedUserName && storedUserId) {
      setUserName(storedUserName);
      setUserId(storedUserId);
    } else {
      setShowUserSetup(true);
    }
  }, []);

  const handleUserSetup = (name: string) => {
    const cleanName = name.trim().toLowerCase().replace(/[^a-z0-9]/g, '');
    const newUserId = `user-${cleanName}-${Date.now()}`;

    setUserName(name);
    setUserId(newUserId);
    setShowUserSetup(false);

    localStorage.setItem('chat-user-name', name);
    localStorage.setItem('chat-user-id', newUserId);
  };

  const handleLogout = () => {
    localStorage.removeItem('chat-user-name');
    localStorage.removeItem('chat-user-id');
    setUserName('');
    setUserId('');
    setMessages([]);
    setShowUserSetup(true);
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading || !userId) return;

    const userMessage: Message = {
      id: uuidv4(),
      text: inputValue,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputValue,
          userId: userId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get response');
      }

      const assistantMessage: Message = {
        id: uuidv4(),
        text: data.response,
        isUser: false,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: uuidv4(),
        text: 'Sorry, I encountered an error. Please try again.',
        isUser: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // User setup component
  const UserSetup = () => {
    const [tempName, setTempName] = useState('');

    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-100 dark:bg-gray-900 p-8">
        <div className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 text-center">
            Welcome to Chat with Memory
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6 text-center">
            Enter your name to start chatting. Your conversations will be remembered across sessions.
          </p>
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Enter your name (e.g., Alice, Bob, John)"
              value={tempName}
              onChange={(e) => setTempName(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && tempName.trim()) {
                  handleUserSetup(tempName);
                }
              }}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              autoFocus
            />
            <button
              onClick={() => tempName.trim() && handleUserSetup(tempName)}
              disabled={!tempName.trim()}
              className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white py-2 px-4 rounded-lg transition-colors"
            >
              Start Chatting
            </button>
          </div>
        </div>
      </div>
    );
  };

  if (showUserSetup) {
    return <UserSetup />;
  }

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Chat with Memory
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Powered by Groq + Hindsight • Welcome back, {userName}!
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 underline"
        >
          Switch User
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
            <p className="text-lg mb-2">👋 Hello {userName}! I'm your AI assistant with memory.</p>
            <p className="text-sm">I remember our past conversations. Ask me what I know about you, or tell me something new!</p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                message.isUser
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
              }`}
            >
              {message.isUser ? (
                <p className="whitespace-pre-wrap">{message.text}</p>
              ) : (
                <div
                  className="prose prose-sm max-w-none dark:prose-invert prose-gray"
                  dangerouslySetInnerHTML={{
                    __html: marked(message.text, {
                      breaks: true,
                      gfm: true
                    })
                  }}
                />
              )}
              <p className={`text-xs mt-1 ${
                message.isUser ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
              }`}>
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-700 px-4 py-2 rounded-lg">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <div className="flex space-x-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message... (Press Enter to send)"
            className="flex-1 resize-none border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!inputValue.trim() || isLoading || !userId}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}