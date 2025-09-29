// AuthContext.jsx
import React, { createContext, useState, useEffect } from 'react';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);

    // Verify token on app start
    useEffect(() => {
        verifyStoredToken();
    }, []);

    const verifyStoredToken = async () => {
        const storedToken = localStorage.getItem('token');
        const storedUser = localStorage.getItem('user');
        
        if (storedToken && storedUser) {
            try {
                const response = await fetch('http://localhost:8000/api/verify', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${storedToken}`
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    setToken(storedToken);
                    setUser(JSON.parse(storedUser));
                } else {
                    // Token is invalid, clear storage
                    localStorage.removeItem('token');
                    localStorage.removeItem('user');
                }
            } catch (error) {
                console.error('Token verification failed:', error);
                localStorage.removeItem('token');
                localStorage.removeItem('user');
            }
        }
        setLoading(false);
    };

    const login = async (newToken, userData) => {
        setToken(newToken);
        setUser(userData);
        localStorage.setItem('token', newToken);
        localStorage.setItem('user', JSON.stringify(userData));
    };

    const logout = async () => {
        try {
            // Call logout endpoint (optional - for server-side cleanup)
            await fetch('http://localhost:8000/api/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        } catch (error) {
            console.error('Logout API call failed:', error);
        } finally {
            // Always clear client-side storage
            setToken(null);
            setUser(null);
            localStorage.removeItem('token');
            localStorage.removeItem('user');
        }
    };

    const value = {
        user,
        token,
        login,
        logout,
        isAuthenticated: !!token,
        verifyToken: verifyStoredToken
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};