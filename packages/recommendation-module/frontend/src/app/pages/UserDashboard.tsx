import { Activity, LogOut, Plus, Server, TestTube, FolderOpen, TrendingUp, Clock, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';

interface Application {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'inactive';
  testCycles: number;
  lastUpdated: string;
  environment: string;
}

export function UserDashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const [applications, setApplications] = useState<Application[]>([
    {
      id: 'hms-001',
      name: 'Hospital Management System',
      description: 'Comprehensive healthcare application for managing patient records and hospital operations',
      status: 'active',
      testCycles: 5,
      lastUpdated: '2 hours ago',
      environment: 'Production'
    },
    {
      id: 'ecom-002',
      name: 'E-Commerce Platform',
      description: 'Full-featured online shopping platform with payment integration',
      status: 'active',
      testCycles: 12,
      lastUpdated: '1 day ago',
      environment: 'Staging'
    },
    {
      id: 'crm-003',
      name: 'Customer Relationship Manager',
      description: 'CRM system for tracking customer interactions and sales pipeline',
      status: 'inactive',
      testCycles: 3,
      lastUpdated: '5 days ago',
      environment: 'Development'
    }
  ]);

  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (!userData) {
      navigate('/login');
    } else {
      setUser(JSON.parse(userData));
    }
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('user');
    navigate('/login');
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Navigation Bar */}
      <nav className="bg-white/90 backdrop-blur-md border-b border-slate-200 px-6 py-4 shadow-md">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
                Chamora Dashboard
              </h1>
              <p className="text-xs text-slate-600">AI Performance Intelligence Engine</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right mr-2">
              <p className="text-sm font-semibold text-slate-800">{user.name}</p>
              <p className="text-xs text-slate-600">{user.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-all"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-6">
        {/* Header Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-3xl font-bold text-slate-800 mb-2">My Applications</h2>
              <p className="text-slate-600">Manage and monitor your registered applications</p>
            </div>
            <Link
              to="/onboarding"
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg"
            >
              <Plus className="w-5 h-5" />
              Register New Application
            </Link>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-4 gap-6 mb-8">
            <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-slate-600">Total Applications</p>
                <Server className="w-5 h-5 text-indigo-600" />
              </div>
              <p className="text-3xl font-bold text-slate-800">{applications.length}</p>
            </div>

            <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-slate-600">Active Apps</p>
                <TrendingUp className="w-5 h-5 text-emerald-600" />
              </div>
              <p className="text-3xl font-bold text-slate-800">
                {applications.filter(app => app.status === 'active').length}
              </p>
            </div>

            <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-slate-600">Total Test Cycles</p>
                <TestTube className="w-5 h-5 text-purple-600" />
              </div>
              <p className="text-3xl font-bold text-slate-800">
                {applications.reduce((sum, app) => sum + app.testCycles, 0)}
              </p>
            </div>

            <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-slate-600">Team Members</p>
                <Users className="w-5 h-5 text-blue-600" />
              </div>
              <p className="text-3xl font-bold text-slate-800">12</p>
            </div>
          </div>
        </div>

        {/* Applications Grid */}
        <div className="grid grid-cols-1 gap-6">
          {applications.map((app) => (
            <div
              key={app.id}
              className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                      app.status === 'active'
                        ? 'bg-gradient-to-br from-indigo-500 to-purple-600'
                        : 'bg-slate-300'
                    }`}>
                      <Server className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-slate-800">{app.name}</h3>
                      <div className="flex items-center gap-3 mt-1">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                          app.status === 'active'
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-slate-200 text-slate-600'
                        }`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${
                            app.status === 'active' ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
                          }`} />
                          {app.status}
                        </span>
                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {app.lastUpdated}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className="text-slate-600 mb-4 ml-15">{app.description}</p>

                  <div className="flex items-center gap-6 text-sm text-slate-600 ml-15">
                    <div className="flex items-center gap-2">
                      <TestTube className="w-4 h-4 text-purple-600" />
                      <span>{app.testCycles} Test Cycles</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Server className="w-4 h-4 text-blue-600" />
                      <span>{app.environment}</span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-3">
                  <Link
                    to={`/application/${app.id}`}
                    className="px-6 py-2.5 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg font-medium text-center whitespace-nowrap"
                  >
                    Open Dashboard
                  </Link>
                  
                  <div className="flex gap-2">
                    <Link
                      to={`/onboarding/${app.id}/2`}
                      className="flex items-center gap-1 px-4 py-2 bg-purple-50 text-purple-700 border border-purple-200 rounded-lg hover:bg-purple-100 transition-all text-sm font-medium"
                    >
                      <TestTube className="w-4 h-4" />
                      Add Tests
                    </Link>
                    <Link
                      to={`/onboarding/${app.id}/3`}
                      className="flex items-center gap-1 px-4 py-2 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-all text-sm font-medium"
                    >
                      <FolderOpen className="w-4 h-4" />
                      Add Docs
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Empty State (when no applications) */}
        {applications.length === 0 && (
          <div className="bg-white/80 backdrop-blur-sm border-2 border-dashed border-slate-300 rounded-xl p-12 text-center">
            <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Server className="w-10 h-10 text-slate-400" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-2">No Applications Yet</h3>
            <p className="text-slate-600 mb-6">Get started by registering your first application</p>
            <Link
              to="/onboarding"
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg"
            >
              <Plus className="w-5 h-5" />
              Register New Application
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
