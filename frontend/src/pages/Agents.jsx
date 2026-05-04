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
    } catch (err) {
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
    } catch (err) {
      alert("Failed to update agent");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this agent?")) return;

    try {
      await API.delete(`/agents/${id}`);
      setAgents((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
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
    <div>
      <div className="flex justify-between mb-6">
        <h1 className="text-2xl font-semibold">Agents</h1>

        <button
          onClick={() => setShowModal(true)}
          className="bg-gray-900 text-white px-4 py-2 rounded"
        >
          + Create Agent
        </button>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : agents.length === 0 ? (
        <p className="text-gray-400">No agents yet</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <div
              key={agent.id}
              onClick={() =>
                setSelectedAgent(
                  selectedAgent?.id === agent.id ? null : agent
                )
              }
              className="bg-white border rounded-lg shadow-sm p-4 hover:shadow-md transition cursor-pointer"
            >
              <h2 className="font-semibold text-lg">{agent.name}</h2>

              <p className="text-sm text-gray-500 mt-1">
                {agent.language || "No language"}
              </p>

              <p className="text-xs text-gray-400 mt-1">
                {agent.llm_model}
              </p>

              <div className="mt-4 text-sm space-y-1">
                <p><b>Voice:</b> {agent.voice || "—"}</p>
                <p><b>Prompt:</b> {agent.system_prompt || "—"}</p>
              </div>

              {/*  NEW: SHOW ID */}
              {selectedAgent?.id === agent.id && (
                <div className="mt-3 text-xs text-gray-500">
                  ID: {agent.id}
                </div>
              )}

              <div className="flex justify-between mt-4">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEdit(agent);
                  }}
                  className="text-blue-600 text-sm"
                >
                  Edit
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(agent.id);
                  }}
                  className="text-red-600 text-sm"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex justify-center items-center">
          <div className="bg-white p-6 rounded-lg w-96 shadow-lg">
            <h2 className="mb-4 font-semibold">
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
                className="bg-gray-900 text-white px-4 py-2 rounded"
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