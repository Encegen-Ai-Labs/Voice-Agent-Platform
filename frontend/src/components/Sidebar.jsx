import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div className="w-60 bg-white border-r p-4">
      <h2 className="text-xl font-semibold mb-6">Voice AI</h2>

      <nav className="flex flex-col gap-3">
        <Link to="/" className="hover:text-blue-600">Dashboard</Link>
        <Link to="/agents" className="hover:text-blue-600">Agents</Link>
        <Link to="/calls" className="hover:text-blue-600">Calls</Link>
        <Link to="/analytics" className="hover:text-blue-600">Analytics</Link>
        <Link to="/settings" className="hover:text-blue-600">Settings</Link>
      </nav>
    </div>
  );
}