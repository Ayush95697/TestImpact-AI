import axios, { AxiosError } from 'axios';

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '');

export class ApiError extends Error {
  status: number | null;
  isNetworkError: boolean;
  detail: string;

  constructor(message: string, status: number | null = null, isNetworkError = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.isNetworkError = isNetworkError;
    this.detail = message;
  }
}

interface ValidationErrorItem {
  loc?: Array<string | number>;
  msg?: string;
}

interface FastAPIErrorBody {
  detail?: string | ValidationErrorItem[];
  message?: string;
}

export function parseApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<FastAPIErrorBody>;
    if (!axiosErr.response) {
      if (axiosErr.code === 'ECONNABORTED') {
        return new ApiError(
          'The backend request timed out. Please verify the service is responsive and retry.',
          null,
          true
        );
      }
      return new ApiError(
        'Unable to reach the FastAPI backend. Please verify the server is running.',
        null,
        true
      );
    }

    const status = axiosErr.response.status;
    const data = axiosErr.response.data;
    let detailMessage = '';

    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') {
        detailMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        detailMessage = data.detail
          .map((item) => {
            const loc = item.loc ? item.loc.slice(1).join('.') : '';
            return loc ? `${loc}: ${item.msg ?? 'Invalid value'}` : (item.msg ?? 'Validation error');
          })
          .join('; ');
      } else if (typeof data.message === 'string') {
        detailMessage = data.message;
      }
    }

    if (!detailMessage) {
      switch (status) {
        case 400:
          detailMessage = 'Invalid request data provided.';
          break;
        case 401:
          detailMessage = 'Authentication with the backend service failed (HTTP 401).';
          break;
        case 403:
          detailMessage = 'Permission denied for the requested operation (HTTP 403).';
          break;
        case 404:
          detailMessage = 'Requested resource was not found.';
          break;
        case 409:
          detailMessage = 'Operation conflicts with existing records or constraints.';
          break;
        case 422:
          detailMessage = 'Input validation failed. Please review your form fields.';
          break;
        case 502:
          detailMessage = 'Upstream AI provider returned an error (HTTP 502). Deterministic records remain unaffected.';
          break;
        case 503:
          detailMessage = 'Requested AI/RAG service is currently unavailable or unconfigured (HTTP 503).';
          break;
        default:
          detailMessage = `Backend error occurred (HTTP ${status}).`;
      }
    }

    return new ApiError(detailMessage, status, false);
  }

  if (error instanceof Error) {
    return new ApiError(error.message, null, false);
  }

  return new ApiError('An unexpected error occurred while communicating with the API.', null, false);
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(parseApiError(error))
);

