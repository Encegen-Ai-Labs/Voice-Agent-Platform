import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState } from "react";

import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";

import Dashboard from "./pages/Dashboard";
import Agents from "./pages/Agents";
import Calls from "./pages/Calls";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import VoiceTest from "./pages/VoiceTest";
import Login from "./pages/Login";
import Register from "./pages/Register";

// 🔒 Protected Route
function PrivateRoute({ children }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" />;
}

// 📦 Layout wrapper
function Layout({ children }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />

      <div className="flex-1 flex flex-col">
        <TopBar />

        <div className="p-6 overflow-auto bg-gray-50 flex-1">
          {children}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* PUBLIC */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* PRIVATE */}
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout>
                <Dashboard />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/agents"
          element={
            <PrivateRoute>
              <Layout>
                <Agents />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/calls"
          element={
            <PrivateRoute>
              <Layout>
                <Calls />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/analytics"
          element={
            <PrivateRoute>
              <Layout>
                <Analytics />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/settings"
          element={
            <PrivateRoute>
              <Layout>
                <Settings />
              </Layout>
            </PrivateRoute>
          }
        />
        <Route
        path="/voice-test"
        element={
          <PrivateRoute>
            <Layout>
              <VoiceTest />
            </Layout>
          </PrivateRoute>
        }
      />


      </Routes>
    </BrowserRouter>
  );
}