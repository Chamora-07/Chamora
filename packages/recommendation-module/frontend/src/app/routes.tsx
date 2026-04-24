import { createBrowserRouter } from "react-router";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { UserDashboard } from "./pages/UserDashboard";
import { ApplicationDashboard } from "./pages/ApplicationDashboard";
import { OnboardingPage } from "./components/OnboardingPage";
import { ChatbotPage } from "./components/ChatbotPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/dashboard",
    element: <UserDashboard />,
  },
  {
    path: "/application/:appId",
    element: <ApplicationDashboard />,
  },
  {
    path: "/onboarding",
    element: <OnboardingPage />,
  },
  {
    path: "/onboarding/:appId/:phase",
    element: <OnboardingPage />,
  },
  {
    path: "/chatbot/:appId",
    element: <ChatbotPage />,
  },
]);
