import axios, { type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "@/modules/auth/authStore";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

// A bare axios call, not `api` — going through `api` here would re-enter this same
// response interceptor and loop forever on a failing refresh.
async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, loginId } = useAuthStore.getState();
  if (!refreshToken) return null;

  try {
    const { data } = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
      refresh_token: refreshToken,
    });
    useAuthStore.getState().setSession({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      role: data.role,
      tenantId: data.tenant_id,
      loginId: data.login_id ?? loginId ?? "",
    });
    return data.access_token as string;
  } catch {
    return null;
  }
}

// Concurrent 401s from multiple in-flight requests share one refresh call instead of
// each firing their own.
let refreshInFlight: Promise<string | null> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || !error.config) {
      return Promise.reject(error);
    }

    const originalRequest = error.config as RetriableRequestConfig;
    const isAuthEndpoint =
      originalRequest.url?.includes("/auth/login") || originalRequest.url?.includes("/auth/refresh");

    if (error.response?.status === 401 && !originalRequest._retried && !isAuthEndpoint) {
      originalRequest._retried = true;

      refreshInFlight ??= refreshAccessToken().finally(() => {
        refreshInFlight = null;
      });
      const newAccessToken = await refreshInFlight;

      if (newAccessToken) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      }

      useAuthStore.getState().clearSession();
      window.location.href = "/login";
    }

    return Promise.reject(error);
  },
);
