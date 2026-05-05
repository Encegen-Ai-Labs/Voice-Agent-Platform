import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";

export default function Register() {
  const [workspace, setWorkspace] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Backend expects: { email, password, workspace_name }
      // Password rules: min 8 chars, 1 uppercase, 1 number, 1 special char
      await API.post(
        "/auth/register",
        {
          email,
          password,
          workspace_name: workspace,
        },
        // No auth header needed — this is a public endpoint
      );

      alert("Registered successfully! Please log in.");
      navigate("/login");
    } catch (err) {
      // FastAPI returns errors as { detail: "..." }
      setError(
        err.response?.data?.detail ?? "Registration failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-100">
      <form onSubmit={handleRegister} className="p-6 bg-white shadow rounded w-80">
        <h2 className="text-xl mb-4 font-semibold">Register</h2>

        {error && (
          <div className="bg-red-100 text-red-600 p-2 mb-3 rounded text-sm">
            {error}
          </div>
        )}

        <input
          type="text"
          placeholder="Workspace Name"
          className="w-full mb-3 p-2 border rounded"
          value={workspace}
          onChange={(e) => setWorkspace(e.target.value)}
          required
        />

        <input
          type="email"
          placeholder="Email"
          className="w-full mb-3 p-2 border rounded"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <input
          type="password"
          placeholder="Password"
          className="w-full mb-1 p-2 border rounded"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {/* Password hint to match backend rules */}
        <p className="text-xs text-gray-400 mb-3">
          Min 8 chars, 1 uppercase, 1 number, 1 special character
        </p>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-500 text-white p-2 rounded"
        >
          {loading ? "Registering..." : "Register"}
        </button>

        <p className="text-sm mt-3 text-center">
          Already a user?{" "}
          <span
            className="text-blue-500 cursor-pointer"
            onClick={() => navigate("/login")}
          >
            Login
          </span>
        </p>
      </form>
    </div>
  );
}
