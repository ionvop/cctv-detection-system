import { request } from './api';
import type { Video, VideoStatus } from '../types';

export interface VideoAnalytics {
  video_id: number;
  filename: string;
  status: string;
  recorded_at: string | null;
  by_type: { object_type: string; count: number }[];
  time_series: { bucket: string; object_type: string; count: number }[];
}

export const videosApi = {
  list: () => request<Video[]>('/videos'),

  getStatus: (videoId: number) =>
    request<VideoStatus>(`/videos/${videoId}/status`),

  getAnalytics: (videoId: number) =>
    request<VideoAnalytics>(`/videos/${videoId}/analytics`),

  upload: (
    file: File,
    intersectionId: number | null,
    recordedAt?: string
  ): Promise<{ video_id: number; job_id: string; status: string; message: string }> => {
    const form = new FormData();
    form.append('file', file);
    if (intersectionId != null) form.append('intersection_id', String(intersectionId));
    if (recordedAt) form.append('recorded_at', recordedAt);

    return request('/videos/upload', {
      method: 'POST',
      body: form,
    });
  },
};
