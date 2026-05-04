import { useEffect, useState } from "react";
import API from "../services/api";

const LLM_MODELS = [
  { label: "Llama 3.3 70B (default)", value: "llama-3.3-70b-versatile" },
  { label: "Llama 3.1 8B", value: "llama-3.1-8b-instant" },
  { label: "Llama 3 70B", value: "llama3-70b-8192" },
  { label: "Llama 3 8B", value: "llama3-8b-8192" },
  { label: "Mixtral 8x7B", value: "mixtral-8x7b-32768" },
  { label: "Gemma 2 9B", value: "gemma2-9b-it" },
];

const EMPTY_FORM = {
  id: "",
  name: "",
  system_prompt: "",
  voice: "",
  language: "",
  llm_model: "llama-3.3-70b-versatile",
};

export default function Agents() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);

  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    try {
      const res = await API.get("/agents");
      setAgents(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!form.name.trim()) return alert("Name required");

    try {
      const res = await API.post("/agents", form);
      setAgents((prev) => [...prev, res.data]);
      resetModal();
    } catch {
      alert("Failed to create agent");
    }
  };

  const handleUpdate = async () => {
    try {
      const res = await API.put(`/agents/${form.id}`, form);
      setAgents((prev) =>
        prev.map((a) => (a.id === form.id ? res.data : a))
      );
      resetModal();
    } catch {
      alert("Failed to update agent");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this agent?")) return;

    try {
      await API.delete(`/agents/${id}`);
      setAgents((prev) => prev.filter((a) => a.id !== id));
    } catch {
      alert("Failed to delete agent");
    }
  };

  const handleEdit = (agent) => {
    setForm(agent);
    setEditing(true);
    setShowModal(true);
  };

  const resetModal = () => {
    setShowModal(false);
    setEditing(false);
    setForm(EMPTY_FORM);
  };

  return (
    <div className="space-y-8">
      
      {/* HEADER */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Agents
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your voice agents and configurations
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="bg-gray-900 text-white px-4 py-2 rounded-lg hover:bg-black transition"
        >
          + New Agent
        </button>
      </div>

      {/* CONTENT */}
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : agents.length === 0 ? (
        <div className="border rounded-xl p-10 text-center text-gray-400 bg-white">
          No agents created yet
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">

          {agents.map((agent) => (
            <div
              key={agent.id}
              onClick={() =>
                setSelectedAgent(
                  selectedAgent?.id === agent.id ? null : agent
                )
              }
              className="group bg-white border rounded-2xl p-5 hover:shadow-lg transition cursor-pointer flex flex-col justify-between"
            >
              
              {/* TOP */}
              <div className="space-y-3">
                <div className="flex justify-between items-start">
                  <h2 className="text-lg font-semibold text-gray-900">
                    {agent.name}
                  </h2>

                  <span className="text-xs text-gray-400">
                    {agent.language || "—"}
                  </span>
                </div>

                <p className="text-xs text-gray-400">
                  {agent.llm_model}
                </p>
              </div>

              {/* PROMPT (SOFT BOX STYLE) */}
              <div className="mt-4 bg-gray-50 border rounded-lg p-3 text-sm text-gray-600 line-clamp-3">
                {agent.system_prompt || "No prompt set"}
              </div>

              {/* DETAILS */}
              <div className="mt-4 text-sm text-gray-600">
                <span className="text-gray-400">Voice:</span>{" "}
                {agent.voice || "—"}
              </div>

              {/* ID */}
              {selectedAgent?.id === agent.id && (
                <div className="mt-3 text-xs text-gray-400 break-all">
                  {agent.id}
                </div>
              )}

              {/* ACTIONS */}
              <div className="flex justify-between items-center mt-5 pt-4 border-t opacity-80 group-hover:opacity-100 transition">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEdit(agent);
                  }}
                  className="text-blue-600 text-sm hover:underline"
                >
                  Edit
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(agent.id);
                  }}
                  className="text-red-500 text-sm hover:underline"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}

        </div>
      )}

      {/* MODAL */}
      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex justify-center items-center">
          <div className="bg-white p-6 rounded-xl w-96 shadow-lg">
            <h2 className="mb-4 font-semibold text-lg">
              {editing ? "Edit Agent" : "Create Agent"}
            </h2>

            <input
              className="w-full mb-3 p-2 border rounded"
              placeholder="Name"
              value={form.name}
              onChange={(e) =>
                setForm({ ...form, name: e.target.value })
              }
            />

            <input
              className="w-full mb-3 p-2 border rounded"
              placeholder="System Prompt"
              value={form.system_prompt}
              onChange={(e) =>
                setForm({ ...form, system_prompt: e.target.value })
              }
            />

            <input
              className="w-full mb-3 p-2 border rounded"
              placeholder="Voice"
              value={form.voice}
              onChange={(e) =>
                setForm({ ...form, voice: e.target.value })
              }
            />

            <input
              className="w-full mb-3 p-2 border rounded"
              placeholder="Language"
              value={form.language}
              onChange={(e) =>
                setForm({ ...form, language: e.target.value })
              }
            />

            <select
              className="w-full mb-4 p-2 border rounded"
              value={form.llm_model}
              onChange={(e) =>
                setForm({ ...form, llm_model: e.target.value })
              }
            >
              {LLM_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>

            <div className="flex justify-end gap-2">
              <button onClick={resetModal}>Cancel</button>

              <button
                onClick={editing ? handleUpdate : handleCreate}
                className="bg-gray-900 text-white px-4 py-2 rounded-lg"
              >
                {editing ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}