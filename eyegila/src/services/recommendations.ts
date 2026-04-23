import { request } from './api';
import type { Recommendation } from '@/types';

export interface RecommendationResponse extends Recommendation {
  intersection_name: string;
}

export const recommendationsApi = {
  list(): Promise<RecommendationResponse[]> {
    return request('/recommendations/');
  },
  generate(intersectionId: number): Promise<RecommendationResponse> {
    return request(`/recommendations/generate/${intersectionId}`, { method: 'POST' });
  },
  generateAll(): Promise<RecommendationResponse[]> {
    return request('/recommendations/generate-all', { method: 'POST' });
  },
  updateNotes(id: number, notes: string | null): Promise<RecommendationResponse> {
    return request(`/recommendations/${id}/notes`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
  },
};
