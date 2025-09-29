// App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext,AuthProvider } from './services/AuthContext';
import Login from './components/Auth/Login';
import Dashboard from './components/dashboard/Dashboard';
import ProtectedRoute from './components/Auth/ProtectedRoute';
import './fontAwesome';
// Add this route to your App.jsx
import CompanyDetails from './components/Company_details/CompanyDetails';
function App() {
    return (
        <AuthProvider>
            <Router>
                <div className="App">
                    <Routes>
                        <Route path="/login" element={<Login />} />
                        <Route 
                            path="/home" 
                            element={
                                <ProtectedRoute>
                                    <Dashboard />
                                </ProtectedRoute>
                            } 
                        />
                          <Route 
                            path="/company/:companyId" 
                            element={
                                <ProtectedRoute>
                                    <CompanyDetails />
                                </ProtectedRoute>
                            } 
                        />
                        <Route path="/" element={<Navigate to="/home" replace />} />
                    </Routes>
                </div>
            </Router>
        </AuthProvider>
    );
}

export default App;