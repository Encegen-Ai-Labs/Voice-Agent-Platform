import { useState } from "react";
import API from "../services/api";
import { useNavigate, Link } from "react-router-dom";

export default function Login() {
  const [form, setForm] = useState({
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleLogin = async () => {
    setError("");
    setLoading(true);

    try {
      const res = await API.post("/auth/login", form);

      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("workspace", form.email);

      navigate("/");
    } catch (err) {
      if (err.response?.status === 429) {
        setError("Too many attempts. Please wait a minute.");
      } else if (err.response?.status === 401) {
        setError("Invalid email or password.");
      } else {
        setError(err.response?.data?.detail ?? "Something went wrong.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-100">
      <div className="bg-white p-6 rounded-lg shadow w-96">
        <h2 className="text-xl font-semibold mb-4 text-center">
          Login
        </h2>

        {error && (
          <div className="bg-red-100 text-red-600 p-2 mb-3 rounded text-sm">
            {error}
          </div>
        )}

        <input
          type="email"
          placeholder="Email"
          className="w-full mb-3 p-2 border rounded"
          value={form.email}
          onChange={(e) =>
            setForm({ ...form, email: e.target.value })
          }
          onKeyDown={(e) => {
            if (e.key === "Enter") handleLogin();
          }}
        />

        <input
          type="password"
          placeholder="Password"
          className="w-full mb-4 p-2 border rounded"
          value={form.password}
          onChange={(e) =>
            setForm({ ...form, password: e.target.value })
          }
          onKeyDown={(e) => {
            if (e.key === "Enter") handleLogin();
          }}
        />

        <button
          onClick={handleLogin}
          disabled={loading}
          className="w-full bg-gray-900 text-white py-2 rounded"
        >
          {loading ? "Logging in..." : "Login"}
        </button>

        <p className="text-sm text-center mt-3">
          Don't have an account?{" "}
          <Link to="/register" className="text-blue-600">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}