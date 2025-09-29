// ProtectedRoute.jsx
import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext, AuthProvider } from '../../services/AuthContext';

const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, user, token } = useContext(AuthContext);
    
    console.log('ProtectedRoute check:', {
        isAuthenticated,
        user: user ? 'User exists' : 'No user',
        token: token ? 'Token exists' : 'No token'
    });
    
    if (!isAuthenticated) {
        console.log('Redirecting to login - not authenticated');
        return <Navigate to="/login" replace />;
    }
    
    return children;
};

export default ProtectedRoute;