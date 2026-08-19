import axios, { type AxiosResponse, type AxiosError } from 'axios';
import type { JsonResult } from '../types/packing';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
});

request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data;
  },
  (error: AxiosError<{ message?: string }>) => {
    const fallbackRes: JsonResult<null> = {
      code: error.response?.status || 500,
      message: error.response?.data?.message || error.message || '网络连接异常',
      data: null,
      timestamp: Date.now(),
    };
    return Promise.resolve(fallbackRes);
  }
);

export default request;