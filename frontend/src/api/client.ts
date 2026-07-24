import axios, { type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "@/store/authStore";
import type { AccessTokenResponse } from "@/types/auth";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Media (logo, etc.) is served by the backend at its origin, not under /api/v1.
// In production, Nginx proxies /media on the same origin as the frontend, so a
// relative logo_url resolves correctly on its own — this only rewrites it when
// the frontend and backend are on different origins (e.g. the Vite dev server).
const mediaOrigin = baseURL.replace(/\/api\/v1\/?$/, "");

export function resolveMediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${mediaOrigin}${path.startsWith("/") ? path : `/${path}`}`;
}

export const apiClient = axios.create({ baseURL });

// Used only for the refresh call itself — must not carry the interceptors
// below, or a failed refresh would recursively try to refresh itself.
const refreshClient = axios.create({ baseURL });

apiClient.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const { refreshToken, setAccessToken, clear } = useAuthStore.getState();
  if (!refreshToken) {
    clear();
    throw new Error("No refresh token available");
  }
  try {
    const { data } = await refreshClient.post<AccessTokenResponse>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    setAccessToken(data.access_token);
    return data.access_token;
  } catch (err) {
    clear();
    throw err;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as RetryableConfig | undefined;
    const url: string = original?.url ?? "";
    const isAuthEndpoint = url.endsWith("/auth/login") || url.endsWith("/auth/refresh");

    if (error.response?.status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        refreshPromise ??= refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
        const token = await refreshPromise;
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${token}`;
        return apiClient(original);
      } catch {
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  },
);
