import { useEffect, useState } from "react";
<<<<<<< HEAD
import { useLocation } from "react-router-dom";

=======
import { useLocation, useNavigate } from "react-router-dom";
import API from "../services/api";
>>>>>>> 873dfff08b49a6083f5b2039f48b375bc1380869

export default function TopBar() {
  const [workspaceName, setWorkspaceName] = useState("");
  const location = useLocation();
  const navigate = useNavigate();

  const titles = {
    "/": "Dashboard",
    "/agents": "Agents",
    "/calls": "Calls",
    "/analytics": "Analytics",
    "/settings": "Settings",
  };

  useEffect(() => {
<<<<<<< HEAD
  const workspace = localStorage.getItem("workspace");
  setWorkspaceName(workspace || "");
}, []);
=======
    const fetchUser = async () => {
      try {
        const res = await API.get("/auth/me");

        // correct field from backend
        setWorkspaceName(res.data.workspace_name);
      } catch (err) {
        console.error(err);
        setWorkspaceName("");
      }
    };

    fetchUser();
  }, []);
>>>>>>> 873dfff08b49a6083f5b2039f48b375bc1380869

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <div className="flex justify-between items-center bg-white border-b px-6 py-3">
      <h1 className="font-semibold text-gray-800">
        {titles[location.pathname] || "Dashboard"}
      </h1>

      <div className="flex items-center gap-4">
        {workspaceName && (
          <span className="text-sm text-gray-600">
            {workspaceName}
          </span>
        )}

        <button
          onClick={handleLogout}
          className="text-red-500 text-sm"
        >
          Logout
        </button>
      </div>
    </div>
  );
}