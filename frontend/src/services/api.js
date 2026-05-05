import axios from "axios";

// Set VITE_API_URL in your .env file, e.g.:
//   VITE_API_URL=http://localhost:8000
// Falls back to localhost:8000 for local dev.
const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

API.interceptors.request.use((req) => {
  const token = localStorage.getItem("token");

  if (token) {
    req.headers.Authorization = `Bearer ${token}`;
  }

  return req;
});

// Global 401 handler — clears token and redirects to login
API.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("workspace");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default API;
