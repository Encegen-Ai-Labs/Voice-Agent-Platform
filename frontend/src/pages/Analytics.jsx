import { useEffect, useState } from "react";
import API from "../services/api";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";

export default function Analytics() {
  const [calls, setCalls] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);

      const callsRes = await API.get("/calls");
      const agentsRes = await API.get("/agents");

      setCalls(callsRes.data);
      setAgents(agentsRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // KPI DATA
  const completedCalls = calls.filter(
    (c) => c.status === "completed"
  ).length;

  const failedCalls = calls.filter(
    (c) => c.status === "failed"
  ).length;

  const resolvedCalls = completedCalls + failedCalls;

  const successRate = resolvedCalls
    ? ((completedCalls / resolvedCalls) * 100).toFixed(1)
    : 0;

  const totalDuration = calls.reduce(
    (acc, c) => acc + (c.duration || 0),
    0
  );
  
  const avgDuration = calls.length
    ? Math.floor(totalDuration / calls.length)
    : 0;

  // CALLS PER DAY
  const callsPerDay = {};

  calls.forEach((c) => {
    if (!c.start_time) return;

    const d = new Date(c.start_time).toLocaleDateString();

    callsPerDay[d] = (callsPerDay[d] || 0) + 1;
  });

  const barData = Object.entries(callsPerDay).map(([date, count]) => ({
    date,
    count,
  }));

  // CALLS PER AGENT
  const agentMap = {};

  calls.forEach((c) => {
    agentMap[c.agent_id] = (agentMap[c.agent_id] || 0) + 1;
  });

  const agentData = Object.entries(agentMap).map(([id, count]) => {
    const agent = agents.find((a) => a.id === id);

    return {
      name: agent?.name || "Unknown",
      calls: count,
    };
  });

  // TOP AGENTS
  const maxCalls = Math.max(
    ...agentData.map((a) => a.calls),
    0
  );

  const topAgents = agentData.filter(
    (a) => a.calls === maxCalls
  );

  const renderAgentTick = ({ x, y, payload }) => {
    const words = String(payload.value).split(" ");

    return (
      <text
        x={x}
        y={y + 10}
        textAnchor="middle"
        fontSize={13}
        fontWeight="700"
      >
        {words.map((word, index) => (
          <tspan key={`${word}-${index}`} x={x} dy={index === 0 ? 0 : 18}>
            {word}
          </tspan>
        ))}
      </text>
    );
  };

  // PEAK HOURS
  const hourMap = {};

  calls.forEach((c) => {
    if (!c.start_time) return;

    const hour = new Date(c.start_time).getHours();

    hourMap[hour] = (hourMap[hour] || 0) + 1;
  });

  const peakHourData = Object.entries(hourMap)
    .map(([hour, count]) => ({
      hour: `${hour}:00`,
      calls: count,
    }))
    .sort((a, b) => b.calls - a.calls);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[70vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-gray-200 border-t-gray-900 rounded-full animate-spin" />

          <p className="text-sm text-gray-500">
            Loading analytics...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">

      {/* HEADER */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900">
            Analytics
          </h1>

          <p className="text-sm text-gray-500 mt-1">
            Monitor call performance and agent activity
          </p>
        </div>

        <div className="bg-white border rounded-full px-4 py-2 text-sm text-gray-600 shadow-sm">
          Live Overview
        </div>
      </div>

      {/* KPI CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">

        <div className="bg-white border rounded-2xl p-5 shadow-sm">
          <p className="text-sm text-gray-500">
            Total Calls
          </p>

          <h2 className="text-3xl font-semibold mt-2">
            {calls.length}
          </h2>
        </div>

        <div className="bg-white border rounded-2xl p-5 shadow-sm">
          <p className="text-sm text-gray-500">
            Failed Calls
          </p>

          <h2 className="text-3xl font-semibold mt-2">
            {failedCalls}
          </h2>
        </div>

        <div className="bg-white border rounded-2xl p-5 shadow-sm">
          <p className="text-sm text-gray-500">
            Success Rate
          </p>

          <h2 className="text-3xl font-semibold mt-2">
            {successRate}%
          </h2>
        </div>

        <div className="bg-white border rounded-2xl p-5 shadow-sm">
          <p className="text-sm text-gray-500">
            Avg Duration
          </p>

          <h2 className="text-3xl font-semibold mt-2">
            {avgDuration}s
          </h2>
        </div>

      </div>

      {/* TOP SECTION */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* CALL VOLUME */}
        <div className="xl:col-span-2 bg-white border rounded-3xl p-6 shadow-sm">

          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Call Volume
            </h2>

            <p className="text-sm text-gray-500">
              Calls handled over time
            </p>
          </div>

          {barData.length === 0 ? (
            <p className="text-sm text-gray-400">
              No analytics data available
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData}>
                <XAxis dataKey="date" />

                <YAxis allowDecimals={false} />

                <Tooltip />

                <Bar
                  dataKey="count"
                  fill="#111827"
                  radius={[8, 8, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* SENTIMENT OVERVIEW */}
        <div className="bg-white border rounded-3xl p-6 shadow-sm">

          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Sentiment Overview
            </h2>

            <p className="text-sm text-gray-500">
              Sentiment analytics will appear once backend processing is available
            </p>
          </div>

          <div className="flex justify-center items-center py-6">
            <div className="relative w-56 h-56">

              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={[
                      {
                        name: "Placeholder",
                        value: 100,
                      },
                    ]}
                    dataKey="value"
                    innerRadius={75}
                    outerRadius={100}
                    startAngle={90}
                    endAngle={-270}
                  >
                    <Cell fill="#d1d5db" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>

              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="text-sm text-gray-400">
                  Sentiment
                </p>

                <h3 className="text-2xl font-semibold text-gray-800">
                  Pending
                </h3>
              </div>

            </div>
          </div>

          <div className="space-y-3 mt-4">

            <div className="flex justify-between text-sm">
              <span className="text-gray-500">
                Positive
              </span>

              <span className="font-medium">
                -
              </span>
            </div>

            <div className="flex justify-between text-sm">
              <span className="text-gray-500">
                Neutral
              </span>

              <span className="font-medium">
                -
              </span>
            </div>

            <div className="flex justify-between text-sm">
              <span className="text-gray-500">
                Negative
              </span>

              <span className="font-medium">
                -
              </span>
            </div>

          </div>
        </div>

      </div>

      {/* LOWER SECTION */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* AGENT ACTIVITY */}
        <div className="bg-white border rounded-3xl p-6 shadow-sm xl:col-span-2">

          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Agent Activity
            </h2>

            <p className="text-sm text-gray-500">
              Calls handled by each agent
            </p>
          </div>

          {agentData.length === 0 ? (
            <p className="text-sm text-gray-400">
              No agent analytics available
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={agentData}>
                <XAxis
                  dataKey="name"
                  interval={0}
                  height={90}
                  tickMargin={18}
                  tick={renderAgentTick}
                />

                <YAxis allowDecimals={false} />

                <Tooltip />

                <Bar
                  dataKey="calls"
                  fill="#6366f1"
                  radius={[8, 8, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* INSIGHTS */}
        <div className="bg-white border rounded-3xl p-6 shadow-sm">

          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Insights
            </h2>

            <p className="text-sm text-gray-500">
              Quick overview of current activity
            </p>
          </div>

          <div className="space-y-5">

            <div className="border rounded-2xl p-4">
              <p className="text-sm text-gray-500">
                Top Performing Agent
              </p>

              <h3 className="text-xl font-semibold mt-1">
                {topAgents.length > 0
                  ? topAgents.map((a) => a.name).join(", ")
                  : "No data"}
              </h3>

              <p className="text-sm text-gray-400 mt-1">
                {maxCalls} calls handled
              </p>
            </div>

            <div className="border rounded-2xl p-4">
              <p className="text-sm text-gray-500">
                Peak Call Hour
              </p>

              <h3 className="text-xl font-semibold mt-1">
                {peakHourData[0]?.hour || "-"}
              </h3>

              <p className="text-sm text-gray-400 mt-1">
                Highest call activity observed
              </p>
            </div>

            <div className="border rounded-2xl p-4">
              <p className="text-sm text-gray-500">
                Active Agents
              </p>

              <h3 className="text-xl font-semibold mt-1">
                {agents.length}
              </h3>

              <p className="text-sm text-gray-400 mt-1">
                Agents currently configured
              </p>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}