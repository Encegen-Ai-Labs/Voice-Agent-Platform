import { useEffect, useState } from "react";
import API from "../services/api";

const statusColor = {
  initiated: "bg-yellow-100 text-yellow-700",
  ongoing: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function Calls() {
  const [calls, setCalls] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  const [expandedCalls, setExpandedCalls] = useState({});
  const [showAgentId, setShowAgentId] = useState({});

  const [form, setForm] = useState({
    agent_id: "",
    phone_number: "",
    direction: "outbound",
  });

  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchCalls();
    fetchAgents();

    const interval = setInterval(() => {
      setCalls((prev) =>
        prev.map((c) => {
          if (c.status === "initiated") return { ...c, status: "ongoing" };
          if (c.status === "ongoing") {
            return {
              ...c,
              status: Math.random() > 0.2 ? "completed" : "failed",
            };
          }
          return c;
        })
      );
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const fetchCalls = async () => {
    try {
      const res = await API.get("/calls");

      const sorted = res.data.sort(
        (a, b) => new Date(b.start_time) - new Date(a.start_time)
      );

      setCalls(sorted);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgents = async () => {
    try {
      const res = await API.get("/agents");
      setAgents(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateCall = async () => {
    if (!form.agent_id) {
      setError("Please select an agent");
      return;
    }

    try {
      const res = await API.post("/calls", form);

      setCalls((prev) => [
        { ...res.data, status: "initiated" },
        ...prev,
      ]);

      setShowModal(false);
      setError("");
    } catch {
      setError("Failed to create call");
    }
  };

  const groupedCalls = agents.map((agent) => ({
    agent,
    calls: calls.filter((c) => c.agent_id === agent.id),
  }));

  return (
    <div className="space-y-6">

      <div className="flex justify-between">
        <h1 className="text-2xl font-semibold">Calls</h1>
        <button
          onClick={() => setShowModal(true)}
          className="bg-gray-900 text-white px-4 py-2 rounded-lg"
        >
          + Create Call
        </button>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="space-y-6">
          {groupedCalls.map(({ agent, calls }) => (
            <div key={agent.id} className="bg-white border rounded-2xl p-5 shadow-sm">

              {/* AGENT HEADER */}
              <div className="flex justify-between items-center mb-3">
                <div>
                  <h2 className="font-semibold text-gray-900">{agent.name}</h2>
                  <p className="text-xs text-gray-500">{calls.length} calls</p>
                </div>

                <button
                  onClick={() =>
                    setShowAgentId((prev) => ({
                      ...prev,
                      [agent.id]: !prev[agent.id],
                    }))
                  }
                  className="text-xs text-blue-600"
                >
                  {showAgentId[agent.id]
                    ? "Hide Agent ID"
                    : "Show Agent ID"}
                </button>
              </div>

              {showAgentId[agent.id] && (
                <div className="text-xs text-gray-400 mb-2 break-all">
                  {agent.id}
                </div>
              )}

              {/* CALL LIST */}
              {calls.length === 0 ? (
                <p className="text-sm text-gray-400">No calls yet</p>
              ) : (
                calls.map((call) => (
                  <div key={call.id} className="border-t py-3">

                    {/* BASIC INFO */}
                    <div
                      className="flex justify-between cursor-pointer"
                      onClick={() =>
                        setExpandedCalls((prev) => ({
                          ...prev,
                          [call.id]: !prev[call.id],
                        }))
                      }
                    >
                      <div className="space-y-1">
                        <p className="font-medium">
                          {call.phone_number || "-"}
                        </p>

                        <p className="text-xs text-gray-400">
                          {call.start_time
                            ? new Date(call.start_time).toLocaleString()
                            : "No time"}
                        </p>

                        <span
                          className={`px-2 py-1 rounded text-xs ${statusColor[call.status] || ""}`}
                        >
                          {call.status}
                        </span>
                      </div>

                      <div className="text-xs text-gray-400">
                        {expandedCalls[call.id] ? "Hide" : "View"}
                      </div>
                    </div>

                    {/* DETAILS */}
                    {expandedCalls[call.id] && (
                      <div className="mt-2 text-sm space-y-2 bg-gray-50 p-3 rounded">

                        <p><b>Direction:</b> {call.direction}</p>

                        <p>
                          <b>Duration:</b>{" "}
                          {call.duration ? `${call.duration}s` : "-"}
                        </p>

                        <p>
                          <b>Sentiment:</b>{" "}
                          {call.sentiment || "-"}
                        </p>

                        <div>
                          <b>Transcript:</b>
                          <div className="text-gray-600 bg-white p-2 rounded border max-h-32 overflow-auto">
                            {call.transcript || "No transcript available"}
                          </div>
                        </div>

                        {call.recording_url && (
                          <a
                            href={call.recording_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600"
                          >
                            Play Recording
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          ))}
        </div>
      )}

      {/* MODAL */}
      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex justify-center items-center">
          <div className="bg-white p-6 rounded-xl w-96 shadow-lg">
            <h2 className="mb-4 font-semibold">Create Call</h2>

            {error && (
              <div className="mb-3 text-sm text-red-500">{error}</div>
            )}

            <select
              className="w-full mb-3 p-2 border rounded"
              value={form.agent_id}
              onChange={(e) =>
                setForm({ ...form, agent_id: e.target.value })
              }
            >
              <option value="">Select Agent</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>

            <input
              className="w-full mb-3 p-2 border rounded"
              placeholder="Phone Number"
              value={form.phone_number}
              onChange={(e) =>
                setForm({ ...form, phone_number: e.target.value })
              }
            />

            <select
              className="w-full mb-4 p-2 border rounded"
              value={form.direction}
              onChange={(e) =>
                setForm({ ...form, direction: e.target.value })
              }
            >
              <option value="outbound">Outbound</option>
              <option value="inbound">Inbound</option>
            </select>

            <div className="flex justify-end gap-2">
              <button onClick={() => setShowModal(false)}>Cancel</button>
              <button
                onClick={handleCreateCall}
                className="bg-gray-900 text-white px-4 py-2 rounded-lg"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}