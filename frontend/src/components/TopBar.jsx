import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import API from "../services/api";

export default function TopBar() {
  const [workspaceName, setWorkspaceName] = useState("");
  const location = useLocation();

  const titles = {
    "/": "Dashboard",
    "/agents": "Agents",
    "/calls": "Calls",
    "/analytics": "Analytics",
    "/settings": "Settings",
  };

  useEffect(() => {
    API.get("/auth/me")
      .then((res) => setWorkspaceName(res.data.workspace_name))
      .catch(() => setWorkspaceName(""));
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("workspace");
    window.location.href = "/login";
  };

  return (
    <div className="flex justify-between items-center bg-white border-b px-6 py-3">
      <h1 className="font-semibold text-gray-800">
        {titles[location.pathname] || "Dashboard"}
      </h1>

      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{workspaceName}</span>
        <button onClick={handleLogout} className="text-red-500 text-sm">
          Logout
        </button>
      </div>
    </div>
  );
}