import axios from 'axios';
import { Source, EvidenceChunk, SystemStatus, ConflictGraphData } from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

export const fetchSystemStatus = async (): Promise<SystemStatus> => {
  const response = await api.get('/system/status');
  return response.data;
};

export const fetchSources = async (): Promise<{ total: number; sources: Source[] }> => {
  const response = await api.get('/sources');
  return response.data;
};

export const uploadSourceFile = async (file: File): Promise<Source> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/sources/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const fetchConflictGraph = async (): Promise<ConflictGraphData> => {
  const response = await api.get('/evidence/graph/conflicts');
  return response.data;
};

export const sendQuery = async (query: string, topK: number = 5) => {
  const response = await api.post('/query', { query, top_k: topK });
  return response.data;
};

export default api;
