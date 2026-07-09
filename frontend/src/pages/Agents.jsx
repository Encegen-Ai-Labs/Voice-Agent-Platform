import { useEffect, useState } from "react";
import API from "../services/api";
import { getVoices } from "../services/voice";
const EMPTY_FORM = {
  id: "",
  name: "",
  system_prompt: "",
  voice: "",
  language: "en",
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
  const [knowledgeBaseFile, setKnowledgeBaseFile] = useState(null);
  const [voices, setVoices] = useState([]);
  const [voicesLoading, setVoicesLoading] = useState(false);
  const [voiceSearch, setVoiceSearch] = useState("");
  const [genderFilter, setGenderFilter] = useState("all");
  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => {
  fetchAgents();
  fetchVoices();
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
  const fetchVoices = async () => {
  try {
    setVoicesLoading(true);

    const data = await getVoices();

    setVoices(data);
  } catch (err) {
    console.error(err);
  } finally {
    setVoicesLoading(false);
  }
};
  const validateForm = () => {
    if (!form.name.trim()) return "Agent name is required";
    if (!form.system_prompt.trim()) return "System prompt is required";
    if (!form.voice.trim()) return "Voice is required";

    return "";
  };

  const handleCreate = async () => {
  const validationError = validateForm();

  if (validationError) {
    setError(validationError);
    return;
  }

  try {
    const payload = {
      ...form,
      language: "en",
      llm_model: "llama-3.3-70b-versatile",
    };

    const res = await API.post("/agents", payload);

    if (knowledgeBaseFile) {
      const formData = new FormData();

      formData.append("file", knowledgeBaseFile);
      formData.append("agent_id", res.data.id);

      await API.post(
        "/knowledge-base",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
    }

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
    setKnowledgeBaseFile(null);
    setForm(EMPTY_FORM);
    setError("");
};
const filteredVoices = voices.filter((voice) => {
  const search = voiceSearch.toLowerCase();
  const normalizedGender = (voice.gender || "").toLowerCase();
  const matchesSearch =
    voice.name.toLowerCase().includes(search) ||
    (voice.description || "").toLowerCase().includes(search);
  const matchesGender =
    genderFilter === "all" ||
    (genderFilter === "female" && normalizedGender.includes("female")) ||
    (genderFilter === "male" && normalizedGender.includes("male"));

  return matchesSearch && matchesGender;
});

const selectedVoice = voices.find(
  (voice) => voice.provider_voice_id === form.voice
);

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

          {agents.map((agent) => {
            const voiceName =
              voices.find((v) => v.provider_voice_id === agent.voice)?.name ||
              agent.voice;

            return (
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
                  {voiceName || "—"}
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
            );
          })}

        </div>
      )}

      {/* CREATE / EDIT MODAL */}
      {showModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-8 py-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">
                {editing ? "Edit Agent" : "Create Agent"}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Configure your agent and choose a voice with a polished, focused experience.
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
              {error && (
                <div className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)] gap-8">
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Agent Details</h3>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      Agent Name
                    </label>
                    <input
                      className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-blue-500"
                      placeholder="Name"
                      value={form.name}
                      onChange={(e) =>
                        setForm({ ...form, name: e.target.value })
                      }
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      System Prompt
                    </label>
                    <textarea
                      rows={10}
                      className="min-h-[250px] w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-blue-500"
                      placeholder="System Prompt"
                      value={form.system_prompt}
                      onChange={(e) =>
                        setForm({ ...form, system_prompt: e.target.value })
                      }
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      Knowledge Base
                    </label>
                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4">
                      <label className="inline-flex cursor-pointer items-center rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                        Upload File
                        <input
                          type="file"
                          accept=".pdf,.txt"
                          className="hidden"
                          onChange={(e) =>
                            setKnowledgeBaseFile(e.target.files?.[0] || null)
                          }
                        />
                      </label>

                      <p className="mt-3 text-sm text-gray-600">
                        {knowledgeBaseFile ? knowledgeBaseFile.name : "No file selected"}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-700">
                        Language
                      </label>
                      <input
                        className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-600"
                        value="English"
                        disabled
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-700">
                        Model
                      </label>
                      <input
                        className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-600"
                        value="llama-3.3-70b-versatile"
                        disabled
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Voice Selection</h3>
                  </div>

                  <div className="rounded-2xl border border-gray-200 bg-gray-50/70 p-4">
                    <input
                      className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-blue-500"
                      placeholder="Search voices..."
                      value={voiceSearch}
                      onChange={(e) => setVoiceSearch(e.target.value)}
                    />

                    <div className="mt-3 flex gap-2">
                      {[
                        { label: "All", value: "all" },
                        { label: "Female", value: "female" },
                        { label: "Male", value: "male" },
                      ].map((filter) => (
                        <button
                          key={filter.value}
                          type="button"
                          onClick={() => setGenderFilter(filter.value)}
                          className={`rounded-full border px-3 py-1.5 text-sm ${
                            genderFilter === filter.value
                              ? "border-blue-600 bg-blue-600 text-white"
                              : "border-gray-200 bg-white text-gray-600 hover:bg-gray-100"
                          }`}
                        >
                          {filter.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-4">
                    <div className="text-sm font-medium text-gray-700">Selected Voice</div>
                    {selectedVoice ? (
                      <div className="mt-3 rounded-2xl border border-blue-200 bg-white p-4">
                        <div className="flex items-center gap-2 text-base font-semibold text-gray-900">
                          <span>🎙</span>
                          <span>{selectedVoice.name}</span>
                        </div>
                        <p className="mt-2 text-sm text-gray-600">
                          {selectedVoice.gender || "Unknown"} • English
                        </p>
                        <p className="mt-2 text-sm text-gray-600">
                          {selectedVoice.description || "No description available"}
                        </p>
                      </div>
                    ) : (
                      <div className="mt-3 rounded-2xl border border-dashed border-gray-200 bg-white p-4 text-sm text-gray-500">
                        No voice selected
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-gray-200 bg-white p-3">
                    <div className="mb-3 text-sm font-medium text-gray-700">Available Voices</div>
                    <div className="max-h-[400px] space-y-2 overflow-y-auto pr-1">
                      {voicesLoading ? (
                        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                          Loading voices...
                        </div>
                      ) : filteredVoices.length === 0 ? (
                        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                          No voices match your search.
                        </div>
                      ) : (
                        filteredVoices.map((voice) => (
                          <button
                            key={voice.id}
                            type="button"
                            onClick={() =>
                              setForm({
                                ...form,
                                voice: voice.provider_voice_id,
                              })
                            }
                            className={`w-full rounded-2xl border p-4 text-left transition ${
                              form.voice === voice.provider_voice_id
                                ? "border-blue-500 bg-blue-50"
                                : "border-gray-200 bg-white hover:border-blue-300 hover:bg-gray-50"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="font-semibold text-gray-900">{voice.name}</div>
                              <span className="text-xs text-gray-500">{voice.gender || "Unknown"}</span>
                            </div>
                            <div className="mt-1 text-sm text-gray-500">English</div>
                            <div className="mt-2 text-sm text-gray-600">
                              {voice.description || "No description available"}
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-gray-200 bg-white px-8 py-5">
              <button
                type="button"
                onClick={resetModal}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={editing ? handleUpdate : handleCreate}
                className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
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