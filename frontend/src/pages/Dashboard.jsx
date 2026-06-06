import { useEffect, useState } from "react";
import API from "../services/api";
import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";

export default function Dashboard() {
  const [stats, setStats] = useState({
    totalAgents: 0,
    totalCalls: 0,
    todayCalls: 0,
  });

  const [recentCalls, setRecentCalls] = useState([]);
  const [peakTime, setPeakTime] = useState([]);
  const [topAgents, setTopAgents] = useState([]);

  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const agentsRes = await API.get("/agents");
      const agents = agentsRes.data;

      const callsRes = await API.get("/calls");
      const calls = callsRes.data;

      const totalAgents = agents.length;
      const totalCalls = calls.length;

      const today = new Date().toDateString();
      const todayCalls = calls.filter(
        (c) =>
          c.start_time &&
          new Date(c.start_time).toDateString() === today
      ).length;

      // Sort calls by latest first before taking top 5
      const sortedCalls = [...calls].sort(
        (a, b) => new Date(b.start_time) - new Date(a.start_time)
      );

      const recent = sortedCalls.slice(0, 6).map((c) => {
        const agent = agents.find((a) => a.id === c.agent_id);
        return {
          id: c.id,
          agent: agent?.name || "Unknown",
          status: c.status,
        };
      });

      const usageMap = {};
      calls.forEach((c) => {
        usageMap[c.agent_id] = (usageMap[c.agent_id] || 0) + 1;
      });

      const top = Object.entries(usageMap)
        .map(([agent_id, count]) => {
          const agent = agents.find((a) => a.id === agent_id);
          return {
            id: agent_id,
            name: agent?.name || "Unknown",
            usage: count,
          };
        })
        .sort((a, b) => b.usage - a.usage)
        .slice(0, 5);

      const hourMap = {};
      calls.forEach((c) => {
        if (!c.start_time) return;
        const hour = new Date(c.start_time).getHours();
        hourMap[hour] = (hourMap[hour] || 0) + 1;
      });

      const peak = Object.entries(hourMap)
        .map(([hour, count]) => ({
          time: `${hour}:00`,
          count,
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);

      setStats({ totalAgents, totalCalls, todayCalls });
      setRecentCalls(recent);
      setTopAgents(top);
      setPeakTime(peak);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Total Agents" value={stats.totalAgents} />
        <StatCard title="Total Calls" value={stats.totalCalls} />
        <StatCard title="Calls Today" value={stats.todayCalls} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <DashboardCard title="Recent Calls" onViewAll={() => navigate("/calls")}>
          {recentCalls.map((c) => (
            <Row key={c.id} left={c.agent} right={c.status} />
          ))}
        </DashboardCard>

        <DashboardCard title="Peak Call Timing" onViewAll={() => navigate("/analytics")}>
          {peakTime.map((p, i) => (
            <Row key={i} left={p.time} right={p.count} />
          ))}
        </DashboardCard>

        <DashboardCard title="Most Used Agents" onViewAll={() => navigate("/agents")}>
          {topAgents.map((a) => (
            <Row key={a.id} left={a.name} right={a.usage} />
          ))}
        </DashboardCard>

      </div>
    </div>
  );
}

function StatCard({ title, value }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-gray-500">{title}</p>
        <h2 className="text-2xl font-semibold">{value}</h2>
      </CardContent>
    </Card>
  );
}

function DashboardCard({ title, children, onViewAll }) {
  return (
    <div className="bg-white border rounded-lg shadow-sm">
      <div className="flex justify-between p-4 border-b">
        <h2>{title}</h2>
        <button onClick={onViewAll}>View All →</button>
      </div>
      <div className="p-4 space-y-2">{children}</div>
    </div>
  );
}

function Row({ left, right }) {
  return (
    <div className="flex justify-between text-sm">
      <span>{left}</span>
      <span>{right}</span>
    </div>
  );
}