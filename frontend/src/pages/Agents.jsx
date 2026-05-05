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
  const [error, setError] = useState("");

  const [deleteTarget, setDeleteTarget] = useState(null);

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

  const validateForm = () => {
    if (!form.name.trim()) return "Agent name is required";
    if (!form.system_prompt.trim()) return "System prompt is required";
    if (!form.voice.trim()) return "Voice is required";
    if (!form.language.trim()) return "Language is required";
    if (!form.llm_model) return "Model selection is required";
    return "";
  };

  const handleCreate = async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      const res = await API.post("/agents", form);
      setAgents((prev) => [...prev, res.data]);
      resetModal();
    } catch {
      setError("Failed to create agent");
    }
  };

  const handleUpdate = async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      const res = await API.put(`/agents/${form.id}`, form);
      setAgents((prev) =>
        prev.map((a) => (a.id === form.id ? res.data : a))
      );
      resetModal();
    } catch {
      setError("Failed to update agent");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      await API.delete(`/agents/${deleteTarget}`);
      setAgents((prev) => prev.filter((a) => a.id !== deleteTarget));
      setDeleteTarget(null);
    } catch {
      setError("Failed to delete agent");
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
    setError("");
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
          className="bg-gray-900 text-white px-4 py-2 rounded-lg"
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
              className="bg-white border rounded-2xl p-5 hover:shadow-lg transition cursor-pointer flex flex-col justify-between"
            >
              
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {agent.name}
                </h2>

                <p className="text-xs text-gray-400 mt-1">
                  {agent.llm_model}
                </p>

                {/* SCROLLABLE PROMPT */}
                <div className="mt-3 bg-gray-50 border rounded-lg p-3 text-sm text-gray-600 max-h-24 overflow-y-auto">
                  {agent.system_prompt || "No prompt set"}
                </div>

                <p className="mt-3 text-sm text-gray-600">
                  <span className="text-gray-400">Voice:</span>{" "}
                  {agent.voice || "—"}
                </p>

                {selectedAgent?.id === agent.id && (
                  <div className="mt-2 text-xs text-gray-400 break-all">
                    {agent.id}
                  </div>
                )}
              </div>

              <div className="flex justify-between mt-4 pt-3 border-t">
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
                    setDeleteTarget(agent.id);
                  }}
                  className="text-red-500 text-sm"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}

        </div>
      )}

      {/* CREATE / EDIT MODAL */}
      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex justify-center items-center">
          <div className="bg-white p-6 rounded-xl w-96 shadow-lg">
            <h2 className="mb-4 font-semibold text-lg">
              {editing ? "Edit Agent" : "Create Agent"}
            </h2>

            {error && (
              <div className="mb-3 text-sm text-red-500">
                {error}
              </div>
            )}

            <input
              className="w-full mb-3 p-2 border rounded"
              placeholder="Name"
              value={form.name}
              onChange={(e) =>
                setForm({ ...form, name: e.target.value })
              }
            />

            <textarea
              rows={4}
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

      {/* DELETE MODAL */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/30 flex justify-center items-center">
          <div className="bg-white p-6 rounded-xl w-80 shadow-lg">
            <h2 className="text-lg font-semibold mb-3">
              Delete Agent
            </h2>

            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to delete this agent?
            </p>

            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteTarget(null)}>
                Cancel
              </button>

              <button
                onClick={handleDelete}
                className="bg-red-500 text-white px-4 py-2 rounded"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}