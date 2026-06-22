import { Activity, AlertCircle, CheckCircle2, Cpu, HardDrive, MessageCircle, User, Clock, Server, ArrowLeft } from 'lucide-react';
import { Link, useParams, useNavigate } from 'react-router';

export function ApplicationDashboard() {
  const { appId } = useParams();
  const navigate = useNavigate();

  // Mock data - in real app, fetch based on appId
  const appName = appId === 'hms-001' ? 'Hospital Management System' : 'Application Dashboard';

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-slate-100">
      {/* Navigation Bar */}
      <nav className="bg-white/80 backdrop-blur-md border-b border-slate-200 px-6 py-4 shadow-sm">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link
              to="/dashboard"
              className="flex items-center justify-center w-10 h-10 bg-slate-100 hover:bg-slate-200 rounded-lg transition-all"
            >
              <ArrowLeft className="w-5 h-5 text-slate-600" />
            </Link>
            <div className="flex items-center gap-3">
              <Activity className="w-6 h-6 text-indigo-600" />
              <h1 className="text-xl font-semibold text-slate-800 tracking-tight">
                {appName}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-lg">
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
            <span className="text-emerald-700 font-medium">Active</span>
          </div>
        </div>
      </nav>

      {/* Main Dashboard Content */}
      <div className="p-6 max-w-[1600px] mx-auto">
        {/* Application Details */}
        <div className="mb-6 bg-white/70 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-600" />
            Application Details
          </h2>
          <div className="grid grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-slate-500 mb-1">Application ID</p>
              <p className="text-slate-800 font-mono">{appId?.toUpperCase()}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Name</p>
              <p className="text-slate-800">{appName}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Domain</p>
              <p className="text-slate-800">Healthcare</p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Environment</p>
              <p className="text-slate-800">Production</p>
            </div>
          </div>
        </div>

        {/* Three Column Grid */}
        <div className="grid grid-cols-3 gap-6 mb-6">
          {/* User Details Card */}
          <div className="bg-white/70 backdrop-blur-sm border border-slate-200 rounded-xl p-6 hover:border-indigo-300 hover:shadow-md transition-all">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
                <User className="w-6 h-6 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700">User Details</h3>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-slate-500">User ID</p>
                <p className="text-slate-800 font-mono">USR-8472</p>
              </div>
              <div>
                <p className="text-sm text-slate-500">User Name</p>
                <p className="text-slate-800">Alex Thompson</p>
              </div>
              <div>
                <p className="text-sm text-slate-500">Applications</p>
                <p className="text-slate-800 text-2xl font-semibold">12</p>
              </div>
            </div>
          </div>

          {/* Center Big Card - Anomaly & Test Cycles */}
          <div className="col-span-2 bg-white/70 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-700 mb-6">Analysis & Testing</h3>

            <div className="grid grid-cols-2 gap-6">
              {/* Anomaly Results */}
              <button className="group bg-gradient-to-br from-amber-50 to-orange-50 hover:from-amber-100 hover:to-orange-100 border border-amber-200 hover:border-amber-300 rounded-lg p-8 transition-all text-left shadow-sm hover:shadow-md">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-slate-700 font-semibold text-lg">Anomaly Results</h4>
                  <AlertCircle className="w-6 h-6 text-amber-600 group-hover:scale-110 transition-transform" />
                </div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-3 h-3 bg-emerald-500 rounded-full" />
                  <span className="text-emerald-600 text-xl font-semibold">Available</span>
                </div>
                <p className="text-sm text-slate-600">Click to view detailed analysis</p>
              </button>

              {/* Test Cycle Comparisons */}
              <button className="group bg-gradient-to-br from-purple-50 to-indigo-50 hover:from-purple-100 hover:to-indigo-100 border border-purple-200 hover:border-purple-300 rounded-lg p-8 transition-all text-left shadow-sm hover:shadow-md">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-slate-700 font-semibold text-lg">Test Cycle Comparisons</h4>
                  <CheckCircle2 className="w-6 h-6 text-purple-600 group-hover:scale-110 transition-transform" />
                </div>
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-purple-600 text-4xl font-bold">5</span>
                  <span className="text-slate-600">cycles</span>
                </div>
                <p className="text-sm text-slate-600">Compare test results across cycles</p>
              </button>
            </div>
          </div>
        </div>

        {/* Testing Environment Info - Bottom Wide Card */}
        <div className="bg-white/70 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <Clock className="w-5 h-5 text-indigo-600" />
            <h3 className="text-lg font-semibold text-slate-700">Testing Environment Info</h3>
          </div>

          <div className="grid grid-cols-4 gap-6">
            {/* Uptime */}
            <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
              <p className="text-sm text-slate-600 mb-2">Uptime</p>
              <p className="text-2xl font-bold text-slate-800">127d 14h</p>
              <p className="text-xs text-slate-500 mt-1">Since last restart</p>
            </div>

            {/* CPU Health */}
            <div className="bg-emerald-50 rounded-lg p-5 border border-emerald-200 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-slate-600">CPU Health</p>
                <Cpu className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-emerald-500 rounded-full" />
                <p className="text-xl font-bold text-emerald-600">Safe</p>
              </div>
              <p className="text-xs text-slate-600 mt-1">Usage: 34%</p>
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-emerald-200">
                <div className="h-full w-[34%] bg-emerald-500" />
              </div>
            </div>

            {/* Storage Health */}
            <div className="bg-amber-50 rounded-lg p-5 border border-amber-200 relative overflow-hidden">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-slate-600">Storage Health</p>
                <HardDrive className="w-4 h-4 text-amber-600" />
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-amber-500 rounded-full animate-pulse" />
                <p className="text-xl font-bold text-amber-600">Risk</p>
              </div>
              <p className="text-xs text-slate-600 mt-1">Usage: 87%</p>
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-amber-200">
                <div className="h-full w-[87%] bg-amber-500" />
              </div>
            </div>

            {/* Additional Info */}
            <div className="bg-blue-50 rounded-lg p-5 border border-blue-200">
              <p className="text-sm text-slate-600 mb-2">Memory</p>
              <p className="text-2xl font-bold text-blue-600">62%</p>
              <p className="text-xs text-slate-600 mt-1">12.4 GB / 20 GB</p>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Chatbot Icon */}
      <Link
        to={`/chatbot/${appId}`}
        className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full shadow-lg hover:shadow-indigo-500/50 hover:scale-110 transition-all flex items-center justify-center group"
      >
        <MessageCircle className="w-6 h-6 text-white group-hover:rotate-12 transition-transform" />
      </Link>
    </div>
  );
}
