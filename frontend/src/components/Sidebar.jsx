import VoiceTest from "@/pages/VoiceTest";
import {
  LayoutDashboard,
  Users,
  Phone,
  BarChart3,
  Settings as SettingsIcon,
  Bot,
  BotMessageSquare,
  BotOff,
  BotMessageSquareIcon,
  TestTube,
  VoteIcon,
  Mic,
  Radio,
  AudioWaveform
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export default function Sidebar({ collapsed, setCollapsed }) {
  const location = useLocation();

  const menu = [
    { name: "Dashboard", path: "/", icon: LayoutDashboard },
    { name: "Agents", path: "/agents", icon: Bot },
    { name: "Calls", path: "/calls", icon: Phone },
    { name: "Analytics", path: "/analytics", icon: BarChart3 },
    { name: "Settings", path: "/settings", icon: SettingsIcon },
    { name: "Voice Testing", path: "/voice-test", icon: AudioWaveform},
  ];

  return (
    <div
      className={`h-screen bg-[#0f172a] text-white flex flex-col transition-all duration-300 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* HEADER */}
      <div className="flex items-center justify-between px-4 py-4">
        {!collapsed && (
          <span className="text-lg font-semibold">Voice AI</span>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-white"
        >
          ☰
        </button>
      </div>

      {/* MENU */}
      <div className="flex flex-col gap-2 px-2">
        {menu.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;

          return (
            <Link
              key={item.name}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-md transition ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <Icon size={18} />

              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </div>
    </div>
  );
}