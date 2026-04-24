import { Activity, ArrowLeft, ArrowRight, Check, Plus, Trash2, Upload, FileText, Server, TestTube, FolderOpen, SkipForward } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';

interface OnboardingPageProps {
  onBackToDashboard?: () => void;
}

interface BlackboxTarget {
  id: string;
  targetName: string;
  containerName: string;
}

interface Phase1Data {
  applicationName: string;
  description: string;
  grafanaEndpoint: string;
  victoriaMetricsEndpoint: string;
  blackboxTargets: BlackboxTarget[];
}

interface Phase2Data {
  applicationName: string;
  testScriptName: string;
  description: string;
  scriptFile: File | null;
  scriptFileName: string;
}

interface Phase3Data {
  applicationName: string;
  documents: Array<{ id: string; file: File; fileName: string }>;
}

export function OnboardingPage({ onBackToDashboard }: OnboardingPageProps) {
  const { appId, phase } = useParams();
  const navigate = useNavigate();
  const [currentPhase, setCurrentPhase] = useState<1 | 2 | 3>(1);
  const [completedPhases, setCompletedPhases] = useState<Set<number>>(new Set());
  const [isEditMode, setIsEditMode] = useState(false);

  // Initialize phase from URL if provided
  useEffect(() => {
    if (phase) {
      const phaseNum = parseInt(phase);
      if (phaseNum >= 1 && phaseNum <= 3) {
        setCurrentPhase(phaseNum as 1 | 2 | 3);
        setIsEditMode(true);
      }
    }
  }, [phase]);

  // Phase 1 State
  const [phase1Data, setPhase1Data] = useState<Phase1Data>({
    applicationName: '',
    description: '',
    grafanaEndpoint: '',
    victoriaMetricsEndpoint: '',
    blackboxTargets: [{ id: '1', targetName: '', containerName: '' }]
  });

  // Phase 2 State
  const [phase2Data, setPhase2Data] = useState<Phase2Data>({
    applicationName: '',
    testScriptName: '',
    description: '',
    scriptFile: null,
    scriptFileName: ''
  });

  // Phase 3 State
  const [phase3Data, setPhase3Data] = useState<Phase3Data>({
    applicationName: '',
    documents: []
  });

  // Phase 1 Functions
  const addBlackboxTarget = () => {
    setPhase1Data({
      ...phase1Data,
      blackboxTargets: [
        ...phase1Data.blackboxTargets,
        { id: Date.now().toString(), targetName: '', containerName: '' }
      ]
    });
  };

  const removeBlackboxTarget = (id: string) => {
    if (phase1Data.blackboxTargets.length > 1) {
      setPhase1Data({
        ...phase1Data,
        blackboxTargets: phase1Data.blackboxTargets.filter(target => target.id !== id)
      });
    }
  };

  const updateBlackboxTarget = (id: string, field: 'targetName' | 'containerName', value: string) => {
    setPhase1Data({
      ...phase1Data,
      blackboxTargets: phase1Data.blackboxTargets.map(target =>
        target.id === id ? { ...target, [field]: value } : target
      )
    });
  };

  // Phase 2 Functions
  const handleScriptFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPhase2Data({
        ...phase2Data,
        scriptFile: file,
        scriptFileName: file.name
      });
    }
  };

  // Phase 3 Functions
  const handleDocumentUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newDocuments = Array.from(files).map(file => ({
        id: Date.now().toString() + Math.random(),
        file,
        fileName: file.name
      }));
      setPhase3Data({
        ...phase3Data,
        documents: [...phase3Data.documents, ...newDocuments]
      });
    }
  };

  const removeDocument = (id: string) => {
    setPhase3Data({
      ...phase3Data,
      documents: phase3Data.documents.filter(doc => doc.id !== id)
    });
  };

  // Navigation Functions
  const handlePhaseSubmit = () => {
    setCompletedPhases(new Set([...completedPhases, currentPhase]));
    if (currentPhase < 3) {
      setCurrentPhase((currentPhase + 1) as 1 | 2 | 3);
    } else {
      // Final submission
      console.log('All phases completed!', { phase1Data, phase2Data, phase3Data });
      alert('Application registered successfully!');
      if (onBackToDashboard) {
        onBackToDashboard();
      } else {
        navigate('/dashboard');
      }
    }
  };

  const handleSkip = () => {
    if (currentPhase < 3) {
      setCurrentPhase((currentPhase + 1) as 1 | 2 | 3);
    } else {
      // Skip on final phase - complete and go back
      console.log('Skipped final phase');
      alert('Changes saved successfully!');
      if (onBackToDashboard) {
        onBackToDashboard();
      } else {
        navigate('/dashboard');
      }
    }
  };

  const goToPhase = (phase: 1 | 2 | 3) => {
    setCurrentPhase(phase);
  };

  const handleBackToDashboard = () => {
    if (onBackToDashboard) {
      onBackToDashboard();
    } else {
      navigate('/dashboard');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Navigation Bar */}
      <nav className="bg-white/90 backdrop-blur-md border-b border-slate-200 px-6 py-4 shadow-md">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-6">
            <button
              onClick={handleBackToDashboard}
              className="flex items-center gap-3 hover:opacity-80 transition-opacity group"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center group-hover:scale-105 transition-transform">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div className="text-left">
                <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
                  {isEditMode ? 'Update Application' : 'Application Onboarding'}
                </h1>
                <p className="text-xs text-slate-600 font-medium">
                  {isEditMode ? 'Add or update application data' : 'Register Your New Application'}
                </p>
              </div>
            </button>
          </div>
          <div className="flex items-center gap-3 px-5 py-2.5 bg-gradient-to-r from-emerald-50 to-green-50 border-2 border-emerald-200 rounded-xl shadow-sm">
            <span className="text-sm text-slate-700 font-medium">Phase {currentPhase} of 3</span>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-xs text-emerald-600 font-semibold">In Progress</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="p-6 max-w-7xl mx-auto">
        {/* Phase Navigation */}
        <div className="mb-8 bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            {[1, 2, 3].map((phase) => (
              <button
                key={phase}
                onClick={() => goToPhase(phase as 1 | 2 | 3)}
                className={`flex-1 flex items-center gap-4 px-6 py-4 rounded-lg transition-all ${
                  currentPhase === phase
                    ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg scale-105'
                    : completedPhases.has(phase)
                    ? 'bg-emerald-50 text-emerald-700 border-2 border-emerald-200'
                    : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'
                } ${phase !== 3 ? 'mr-4' : ''}`}
              >
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                  currentPhase === phase
                    ? 'bg-white/20'
                    : completedPhases.has(phase)
                    ? 'bg-emerald-500 text-white'
                    : 'bg-slate-200 text-slate-600'
                }`}>
                  {completedPhases.has(phase) ? <Check className="w-5 h-5" /> : phase}
                </div>
                <div className="text-left">
                  <p className="font-semibold">
                    {phase === 1 ? 'Application Data' : phase === 2 ? 'Test Cycles' : 'Documents'}
                  </p>
                  <p className={`text-xs ${currentPhase === phase ? 'text-white/80' : 'text-slate-500'}`}>
                    {phase === 1 ? 'Basic information' : phase === 2 ? 'Test scripts' : 'Related files'}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Phase 1: Application Data */}
        {currentPhase === 1 && (
          <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-8 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Server className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Application Details</h2>
                <p className="text-sm text-slate-600">Provide your application's basic information and configuration</p>
              </div>
            </div>

            <div className="space-y-6">
              {/* Application Name */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Application Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={phase1Data.applicationName}
                  onChange={(e) => setPhase1Data({ ...phase1Data, applicationName: e.target.value })}
                  placeholder="Enter application name"
                  className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Description
                </label>
                <textarea
                  value={phase1Data.description}
                  onChange={(e) => setPhase1Data({ ...phase1Data, description: e.target.value })}
                  placeholder="Enter application description"
                  rows={3}
                  className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all resize-none"
                />
              </div>

              {/* Endpoints Grid */}
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Grafana Endpoint of Test Environment
                  </label>
                  <input
                    type="text"
                    value={phase1Data.grafanaEndpoint}
                    onChange={(e) => setPhase1Data({ ...phase1Data, grafanaEndpoint: e.target.value })}
                    placeholder="https://grafana.example.com"
                    className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Victoria Metrics Endpoint of Test Environment
                  </label>
                  <input
                    type="text"
                    value={phase1Data.victoriaMetricsEndpoint}
                    onChange={(e) => setPhase1Data({ ...phase1Data, victoriaMetricsEndpoint: e.target.value })}
                    placeholder="https://victoria-metrics.example.com"
                    className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all"
                  />
                </div>
              </div>

              {/* Blackbox Targets Table */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <label className="block text-sm font-semibold text-slate-700">
                    Blackbox Targets Configuration
                  </label>
                  <button
                    onClick={addBlackboxTarget}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg"
                  >
                    <Plus className="w-4 h-4" />
                    Add Target
                  </button>
                </div>

                <div className="border-2 border-slate-200 rounded-lg overflow-hidden">
                  <div className="bg-slate-100 grid grid-cols-12 gap-4 px-4 py-3 font-semibold text-sm text-slate-700 border-b-2 border-slate-200">
                    <div className="col-span-5">Blackbox Target Name</div>
                    <div className="col-span-5">Container Name</div>
                    <div className="col-span-2 text-center">Actions</div>
                  </div>

                  <div className="bg-white divide-y divide-slate-200">
                    {phase1Data.blackboxTargets.map((target, index) => (
                      <div key={target.id} className="grid grid-cols-12 gap-4 px-4 py-3 items-center">
                        <div className="col-span-5">
                          <input
                            type="text"
                            value={target.targetName}
                            onChange={(e) => updateBlackboxTarget(target.id, 'targetName', e.target.value)}
                            placeholder="Target name"
                            className="w-full bg-slate-50 border border-slate-300 focus:border-indigo-400 rounded px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
                          />
                        </div>
                        <div className="col-span-5">
                          <input
                            type="text"
                            value={target.containerName}
                            onChange={(e) => updateBlackboxTarget(target.id, 'containerName', e.target.value)}
                            placeholder="Container name"
                            className="w-full bg-slate-50 border border-slate-300 focus:border-indigo-400 rounded px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
                          />
                        </div>
                        <div className="col-span-2 flex justify-center">
                          <button
                            onClick={() => removeBlackboxTarget(target.id)}
                            disabled={phase1Data.blackboxTargets.length === 1}
                            className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-6 border-t-2 border-slate-200">
                <button
                  onClick={handleSkip}
                  className="flex items-center gap-2 px-6 py-3 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-all"
                >
                  <SkipForward className="w-4 h-4" />
                  Skip for Now
                </button>
                <button
                  onClick={handlePhaseSubmit}
                  disabled={!phase1Data.applicationName}
                  className="flex items-center gap-2 px-8 py-3 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Submit & Continue
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Phase 2: Test Cycles */}
        {currentPhase === 2 && (
          <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-8 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg flex items-center justify-center">
                <TestTube className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Test Cycles Configuration</h2>
                <p className="text-sm text-slate-600">Upload JMeter test scripts and provide test cycle details</p>
              </div>
            </div>

            <div className="space-y-6">
              {/* Application Name */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Application Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={phase2Data.applicationName}
                  onChange={(e) => setPhase2Data({ ...phase2Data, applicationName: e.target.value })}
                  placeholder="Enter application name"
                  className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all"
                />
              </div>

              {/* Test Script Name */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Test Script Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={phase2Data.testScriptName}
                  onChange={(e) => setPhase2Data({ ...phase2Data, testScriptName: e.target.value })}
                  placeholder="Enter test script name"
                  className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Description
                </label>
                <textarea
                  value={phase2Data.description}
                  onChange={(e) => setPhase2Data({ ...phase2Data, description: e.target.value })}
                  placeholder="Enter test script description"
                  rows={3}
                  className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all resize-none"
                />
              </div>

              {/* File Upload */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Upload Test Script File (JMeter) <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="file"
                    accept=".jmx,.xml"
                    onChange={handleScriptFileUpload}
                    className="hidden"
                    id="script-upload"
                  />
                  <label
                    htmlFor="script-upload"
                    className="flex items-center justify-center gap-3 w-full bg-gradient-to-br from-indigo-50 to-purple-50 border-2 border-dashed border-indigo-300 hover:border-indigo-400 rounded-lg px-6 py-8 cursor-pointer transition-all hover:bg-gradient-to-br hover:from-indigo-100 hover:to-purple-100"
                  >
                    <Upload className="w-8 h-8 text-indigo-600" />
                    <div className="text-center">
                      <p className="font-semibold text-slate-700">
                        {phase2Data.scriptFileName || 'Click to upload or drag and drop'}
                      </p>
                      <p className="text-sm text-slate-500 mt-1">JMX or XML files only</p>
                    </div>
                  </label>
                </div>
                {phase2Data.scriptFileName && (
                  <div className="mt-3 flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <FileText className="w-4 h-4 text-emerald-600" />
                    <span className="text-sm text-emerald-700 font-medium">{phase2Data.scriptFileName}</span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-6 border-t-2 border-slate-200">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setCurrentPhase(1)}
                    className="flex items-center gap-2 px-6 py-3 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-all"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back
                  </button>
                  <button
                    onClick={handleSkip}
                    className="flex items-center gap-2 px-6 py-3 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-all"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip for Now
                  </button>
                </div>
                <button
                  onClick={handlePhaseSubmit}
                  disabled={!phase2Data.applicationName || !phase2Data.testScriptName || !phase2Data.scriptFile}
                  className="flex items-center gap-2 px-8 py-3 bg-gradient-to-br from-purple-500 to-pink-600 text-white rounded-lg hover:from-purple-600 hover:to-pink-700 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Submit & Continue
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Phase 3: Documents */}
        {currentPhase === 3 && (
          <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-8 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center">
                <FolderOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Application Documents</h2>
                <p className="text-sm text-slate-600">Upload relevant documents and resources for your application</p>
              </div>
            </div>

            <div className="space-y-6">
              {/* Application Name */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Application Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={phase3Data.applicationName}
                  onChange={(e) => setPhase3Data({ ...phase3Data, applicationName: e.target.value })}
                  placeholder="Enter application name"
                  className="w-full bg-white border-2 border-slate-300 focus:border-indigo-400 rounded-lg px-4 py-3 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 transition-all"
                />
              </div>

              {/* Document Upload */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Upload Documents
                </label>
                <div className="relative">
                  <input
                    type="file"
                    multiple
                    onChange={handleDocumentUpload}
                    className="hidden"
                    id="document-upload"
                  />
                  <label
                    htmlFor="document-upload"
                    className="flex items-center justify-center gap-3 w-full bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-dashed border-emerald-300 hover:border-emerald-400 rounded-lg px-6 py-12 cursor-pointer transition-all hover:bg-gradient-to-br hover:from-emerald-100 hover:to-teal-100"
                  >
                    <Upload className="w-10 h-10 text-emerald-600" />
                    <div className="text-center">
                      <p className="font-semibold text-slate-700 text-lg">Click to upload or drag and drop</p>
                      <p className="text-sm text-slate-500 mt-1">PDF, DOC, DOCX, TXT, or any other document types</p>
                      <p className="text-xs text-slate-400 mt-2">You can select multiple files at once</p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Uploaded Documents List */}
              {phase3Data.documents.length > 0 && (
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-3">
                    Uploaded Documents ({phase3Data.documents.length})
                  </label>
                  <div className="space-y-2">
                    {phase3Data.documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                            <FileText className="w-5 h-5 text-emerald-600" />
                          </div>
                          <div>
                            <p className="font-medium text-slate-800">{doc.fileName}</p>
                            <p className="text-xs text-slate-500">{(doc.file.size / 1024).toFixed(2)} KB</p>
                          </div>
                        </div>
                        <button
                          onClick={() => removeDocument(doc.id)}
                          className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-6 border-t-2 border-slate-200">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setCurrentPhase(2)}
                    className="flex items-center gap-2 px-6 py-3 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-all"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back
                  </button>
                  <button
                    onClick={handleSkip}
                    className="flex items-center gap-2 px-6 py-3 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-all"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip & Complete
                  </button>
                </div>
                <button
                  onClick={handlePhaseSubmit}
                  disabled={!phase3Data.applicationName}
                  className="flex items-center gap-2 px-8 py-3 bg-gradient-to-br from-emerald-500 to-teal-600 text-white rounded-lg hover:from-emerald-600 hover:to-teal-700 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Complete Registration
                  <Check className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}