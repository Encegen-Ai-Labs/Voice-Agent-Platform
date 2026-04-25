import { Link, useLocation } from "react-router-dom";

export default function Sidebar({ collapsed, setCollapsed }) {
  const location = useLocation();

  const menu = [
    { name: "Dashboard", path: "/" },
    { name: "Agents", path: "/agents" },
    { name: "Calls", path: "/calls" },
    { name: "Analytics", path: "/analytics" },
    { name: "Settings", path: "/settings" },
  ];

  return (
    <div className={`bg-white border-r transition-all duration-300 ${collapsed ? "w-16" : "w-56"}`}>
      <div className="h-16 flex items-center justify-between px-4 border-b">
        {!collapsed && <span className="font-semibold">Voice AI</span>}
        <button onClick={() => setCollapsed(!collapsed)} className="text-gray-600">
          ☰
        </button>
      </div>
      <div className="p-2 space-y-1">
        {menu.map((item) => (
          <Link
            key={item.name}
            to={item.path}
            className={`block px-3 py-2 rounded text-sm ${
              location.pathname === item.path
                ? "bg-gray-900 text-white"
                : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            {collapsed ? item.name[0] : item.name}
          </Link>
        ))}
      </div>
    </div>
  );
}