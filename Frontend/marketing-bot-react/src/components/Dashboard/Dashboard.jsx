// components/Home.jsx
import React, { useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../../services/AuthContext';
import './Dashboard.css';
import logo from "../../assets/imgs/logo/logo.png";
import { Link } from 'react-router-dom';

const Dashboard = () => {
    const { user, logout } = useContext(AuthContext);
    const navigate = useNavigate();
    
    // State for home data
    const [homeData, setHomeData] = useState({
        companies: [],
        total_budget: 0,
        total_approved: 0,
        total_archived: 0,
        total_strategies: 0
    });
    
    // State for analytics
    const [activePlatform, setActivePlatform] = useState('facebook');
    const [analyticsData, setAnalyticsData] = useState({});
    const [loading, setLoading] = useState(true);
    const [analyticsLoading, setAnalyticsLoading] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    // Chart containers refs
  
    const toggleSidebar = () => {
        setSidebarOpen(!sidebarOpen);
    };
    const handleLogout = async () => {
        await logout();
        navigate('/login');
    };

    const toggleDropdown = () => {
        setDropdownOpen(!dropdownOpen);
    };

    const handleMouseEnter = () => {
        setDropdownOpen(true);
    };

    const handleMouseLeave = () => {
        setDropdownOpen(false);
    };

    // Time-based greeting
    const getTimeGreeting = () => {
        const now = new Date();
        const hour = now.getHours();
        let greeting;
        
        if (hour < 12) {
            greeting = `Good morning`;
        } else if (hour < 18) {
            greeting = `Good afternoon`;
        } else {
            greeting = `Good evening`;
        }
        
        return `${greeting}, ${user?.full_name}`;
    };

    // Fetch home data
    useEffect(() => {
        const fetchHomeData = async () => {
            try {
                setLoading(true);
                const token = localStorage.getItem('token');
                const response = await fetch('http://localhost:8000/api/home', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        setHomeData({
                            companies: data.companies || [],
                            total_budget: data.total_budget || 0,
                            total_approved: data.total_approved || 0,
                            total_archived: data.total_archived || 0,
                            total_strategies: data.total_strategies || 0
                        });
                    }
                }
            } catch (error) {
                console.error('Error fetching home data:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchHomeData();
    }, []);

    // Fetch analytics data
    const fetchAnalyticsData = async (platform, days) => {
        setAnalyticsLoading(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`http://localhost:8000/get_${platform}_analytics?days=${days}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                setAnalyticsData(prev => ({
                    ...prev,
                    [platform]: data
                }));
                
                // Render charts after data is loaded
                setTimeout(() => {
                    renderChartsForPlatform(platform, data);
                }, 100);
            }
        } catch (error) {
            console.error(`Error fetching ${platform} analytics:`, error);
        } finally {
            setAnalyticsLoading(false);
        }
    };

    // Platform toggle handler
    const handlePlatformToggle = (platform) => {
        setActivePlatform(platform);
        if (!analyticsData[platform]) {
            const days = platform === 'instagram' ? 14 : 30;
            fetchAnalyticsData(platform, days);
        } else {
            // Re-render charts if data already exists
            setTimeout(() => {
                renderChartsForPlatform(platform, analyticsData[platform]);
            }, 100);
        }
    };

    // Period change handler
    const handlePeriodChange = (platform, days) => {
        fetchAnalyticsData(platform, days);
    };

    // Simple chart rendering with dynamic import
    const renderChartsForPlatform = async (platform, data) => {
        if (!data) return;

        try {
            // Dynamic import Chart.js to avoid conflicts
            const { Chart, registerables } = await import('chart.js');
            Chart.register(...registerables);

            // Clear existing charts by removing and recreating containers
            const chartIds = getChartIdsForPlatform(platform);
            
            chartIds.forEach(chartId => {
                const container = document.getElementById(chartId + '-container');
                if (container) {
                    container.innerHTML = `<canvas id="${chartId}" width="400" height="250"></canvas>`;
                }
            });

            // Small delay to ensure DOM is updated
            setTimeout(() => {
                if (platform === 'facebook') {
                    createFacebookCharts(Chart, data);
                } else if (platform === 'instagram') {
                    createInstagramCharts(Chart, data);
                } else if (platform === 'linkedin') {
                    createLinkedInCharts(Chart, data);
                }
            }, 50);

        } catch (error) {
            console.error('Error loading Chart.js or rendering charts:', error);
        }
    };

    const getChartIdsForPlatform = (platform) => {
        const chartIds = {
            facebook: ['fb-fans-chart', 'fb-engagement-chart', 'fb-reach-chart'],
            instagram: ['ig-followers-chart', 'ig-views-reach-chart', 'ig-profile-activity-chart'],
            linkedin: ['ln-connections-chart', 'ln-views-impressions-chart']
        };
        return chartIds[platform] || [];
    };

    const createFacebookCharts = (Chart, data) => {
        // Fans Growth Chart
        createLineChart(Chart, 'fb-fans-chart', 'Page Fans Growth', {
            labels: data.fans_data?.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            datasets: [{
                label: 'Total Fans',
                data: data.fans_data?.values || [1000, 1200, 1100, 1300, 1400],
                borderColor: '#4267B2',
                backgroundColor: 'rgba(66, 103, 178, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 2
            }]
        });

        // Engagement Chart
        createLineChart(Chart, 'fb-engagement-chart', 'Impressions vs Engagement', {
            labels: data.impressions_data?.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            datasets: [
                {
                    label: 'Impressions',
                    data: data.impressions_data?.values || [5000, 6000, 5500, 7000, 7500],
                    borderColor: '#8B9DC3',
                    backgroundColor: 'rgba(139, 157, 195, 0.1)',
                    borderWidth: 2
                },
                {
                    label: 'Engagement',
                    data: data.engagement_data?.values || [500, 600, 550, 700, 750],
                    borderColor: '#3B5998',
                    backgroundColor: 'rgba(59, 89, 152, 0.1)',
                    borderWidth: 2
                }
            ]
        });

        // Reach & Views Chart
        createLineChart(Chart, 'fb-reach-chart', 'Reach & Views', {
            labels: data.reach_data?.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            datasets: [
                {
                    label: 'Reach',
                    data: data.reach_data?.values || [3000, 3500, 3200, 3800, 4000],
                    borderColor: '#1877F2',
                    backgroundColor: 'rgba(24, 119, 242, 0.1)',
                    fill: true,
                    borderWidth: 2
                },
                {
                    label: 'Views',
                    data: data.views_data?.values || [2000, 2200, 2100, 2400, 2500],
                    borderColor: '#42B883',
                    backgroundColor: 'rgba(66, 184, 131, 0.1)',
                    fill: true,
                    borderWidth: 2
                }
            ]
        });
    };

    const createInstagramCharts = (Chart, data) => {
        // Followers Growth Chart
        createLineChart(Chart, 'ig-followers-chart', 'Followers Growth Trend', {
            labels: data.followers_data?.labels || ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
            datasets: [{
                label: 'Followers',
                data: data.followers_data?.values || [1500, 1600, 1550, 1700],
                borderColor: '#E4405F',
                backgroundColor: 'rgba(228, 64, 95, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        });

        // Views & Reach Chart
        createLineChart(Chart, 'ig-views-reach-chart', 'Views & Reach Analytics', {
            labels: data.views_data?.labels || ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
            datasets: [
                {
                    label: 'Total Views',
                    data: data.views_data?.values || [8000, 8500, 8200, 9000],
                    borderColor: '#F77737',
                    backgroundColor: 'rgba(247, 119, 55, 0.1)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2
                },
                {
                    label: 'Accounts Reached',
                    data: data.reach_data?.values || [6000, 6500, 6200, 7000],
                    borderColor: '#833AB4',
                    backgroundColor: 'rgba(131, 58, 180, 0.1)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2
                }
            ]
        });

        // Profile Activity Chart
        createLineChart(Chart, 'ig-profile-activity-chart', 'Profile Activity Overview', {
            labels: data.profile_activity_data?.labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            datasets: [{
                label: 'Profile Views',
                data: data.profile_activity_data?.values || [150, 200, 180, 220, 190],
                borderColor: '#FD1D1D',
                backgroundColor: 'rgba(253, 29, 29, 0.2)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        });
    };

    const createLinkedInCharts = (Chart, data) => {
        // Connections Growth Chart
        createLineChart(Chart, 'ln-connections-chart', 'Connections Growth', {
            labels: data.connections_data?.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            datasets: [{
                label: 'Connections',
                data: data.connections_data?.values || [500, 550, 525, 600, 625],
                borderColor: '#0077B5',
                backgroundColor: 'rgba(0, 119, 181, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 2
            }]
        });

        // Views & Impressions Chart
        createLineChart(Chart, 'ln-views-impressions-chart', 'Profile Views & Post Impressions', {
            labels: data.views_data?.labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            datasets: [
                {
                    label: 'Profile Views',
                    data: data.views_data?.values || [300, 350, 325, 400, 425],
                    borderColor: '#0077B5',
                    backgroundColor: 'rgba(0, 119, 181, 0.15)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2
                },
                {
                    label: 'Post Impressions',
                    data: data.impressions_data?.values || [2000, 2200, 2100, 2400, 2500],
                    borderColor: '#005885',
                    backgroundColor: 'rgba(0, 88, 133, 0.15)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2
                }
            ]
        });
    };

    const createLineChart = (Chart, elementId, title, chartData) => {
        const canvas = document.getElementById(elementId);
        if (!canvas) {
            console.warn(`Canvas element ${elementId} not found`);
            return;
        }

        try {
            new Chart(canvas, {
                type: 'line',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: title,
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        legend: {
                            position: 'bottom',
                            labels: {
                                usePointStyle: true,
                                padding: 20
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.05)'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            });
        } catch (error) {
            console.error(`Error creating chart ${elementId}:`, error);
        }
    };

    // Format numbers
    const formatNumber = (num) => {
        if (!num && num !== 0) return '--';
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    };

    // Initialize analytics on component mount
    useEffect(() => {
        fetchAnalyticsData('facebook', 30);
    }, []);

    if (loading) {
        return (
            <div className="home-page">
                <div className="loading-container">
                    <div className="loading-spinner"></div>
                    <p>Loading dashboard...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="home-page">
            {/* Top Navigation Bar */}
            <nav className="top-nav">
                <div className="nav-container">
                    <div className="nav-left">
                        <button className="sidebar-toggle" onClick={toggleSidebar}>
                            <i className="fas fa-bars"></i>
                        </button>
                        <a href="/" className="logo">
                            <img src={logo} alt="Chahbander" className="logo-img" />
                        </a>
                    </div>
                    <div className="nav-right">
                        <a href="/Company_form" className="btn-primary" style={{display: 'none'}}>
                            <i className="fas fa-plus"></i> Add New Service
                        </a>
                     
                       <div className="user-menu" 
                            onMouseEnter={handleMouseEnter} 
                            onMouseLeave={handleMouseLeave}
                        >
                            <div className="user-avatar" 
                                title={user?.full_name}
                                onClick={toggleDropdown}
                            >
                                {user?.full_name?.[0]?.toUpperCase()}
                            </div>
                            <div className={`dropdown-menu ${dropdownOpen ? 'show' : ''}`}>
                                <a href="/home" className="dropdown-item">
                                    <i className="fas fa-user"></i> {user?.full_name}
                                </a>
                                <a href="/user_settings" className="dropdown-item">
                                    <i className="fas fa-cog"></i> User Settings
                                </a>
                                <a href="#logout" className="dropdown-item logout" onClick={handleLogout}>
                                    <i className="fas fa-sign-out-alt"></i> Logout
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </nav>

            {/* Sidebar */}
            <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
                <ul className="sidebar-menu">
                    <li><Link to="/home" className="nav-link active"><i className="fas fa-chart-line"></i> Dashboard</Link></li>
                    
                    {homeData.companies.map(company => (
                        <React.Fragment key={company.id}>
                            
                            <li><Link to={`/company/${company.id}`} className="nav-link">
                                    <i className="fas fa-building"></i> Company
                                </Link></li>
                            <li><Link to={`/company/${company.id}#strategies`} className="nav-link"><i className="fas fa-lightbulb"></i> Generated Strategies</Link></li>
                        </React.Fragment>
                    ))}
                    
                    <li><Link to="/user_settings" className="nav-link"><i className="fas fa-cog"></i> User Settings</Link></li>
                    <li><a href="#logout" className="nav-link-logout" onClick={handleLogout}><i className="fas fa-sign-out-alt"></i> Logout</a></li>
                </ul>
            </aside>

            {/* Main Content */}
            <main className="main-content">
                <div className="header">
                    <h1 id="timeGreeting" style={{fontSize: '1.8rem'}}>
                        <b>{getTimeGreeting()}</b>
                    </h1>
                </div>
                
                <div className="dashboard-container">
                    {/* Company Card */}
                    {homeData.companies.length > 0 ? (
                        homeData.companies.map(company => (
                            <div key={company.id} className="stat-card">
                                <div className="card-icon company"><i className="fas fa-building"></i></div>
                                <Link to={`/company/${company.id}`} style={{textDecoration: 'none'}}>
                                    <div className="card-content">
                                        <div className="card-title">Company</div>
                                        <div className="card-main">{company.name}</div>
                                        <div className="card-subtitle">Created on: {company.created_at}</div>
                                    </div>
                                </Link>
                            </div>
                        ))
                    ) : (
                        <div className="stat-card">
                            <div className="card-icon company"><i className="fas fa-building"></i></div>
                            <div className="card-content">
                                <div className="card-title">Company</div>
                                <div className="card-main">No companies yet</div>
                                <div className="card-subtitle">Create your business profile</div>
                            </div>
                        </div>
                    )}

                    {/* Strategies Card */}
                    <div className="stat-card">
                        <div className="card-icon strategies"><i className="fas fa-rocket"></i></div>
                        {homeData.companies.length > 0 ? (
                            <Link to={`/company/${homeData.companies[0]?.id}#Strategies`} className="nav-link" style={{textDecoration: 'none'}}>
                                <div className="card-content">
                                    <div className="card-title">Generated Strategies</div>
                                    <div className="card-main">{homeData.total_strategies}</div>
                                    <div className="card-subtitle">
                                        {homeData.total_approved} Approved <i className="fas fa-check" style={{color: 'green'}}></i> 
                                        &nbsp; • &nbsp; 
                                        {homeData.total_archived} Archived <i className="fas fa-archive"></i>
                                    </div>
                                </div>
                            </Link>
                        ) : (
                            <div className="card-content">
                                <div className="card-title">Generated Strategies</div>
                                <div className="card-main">0</div>
                                <div className="card-subtitle">No strategies available</div>
                            </div>
                        )}
                    </div>

                    {/* Budget Card */}
                    <div className="stat-card">
                        <div className="card-icon budget"><i className="fa-solid fa-money-bill"></i></div>
                        <div className="card-content">
                            <div className="card-title">Budget</div>
                            <div className="card-main">{homeData.total_budget.toFixed(2)} TND</div>
                            <div className="card-subtitle">Total allocated budget</div>
                        </div>
                    </div>
                </div>

                {/* Analytics Dashboard */}
                <div className="analytics-header">
                    <h2><i className="fas fa-chart-network"></i> Social Media Analytics</h2>
                    <div className="platform-toggle">
                        <button 
                            className={`toggle-btn ${activePlatform === 'facebook' ? 'active' : ''}`}
                            onClick={() => handlePlatformToggle('facebook')}
                        >
                            <i className="fab fa-facebook"></i> Facebook
                        </button>
                        <button 
                            className={`toggle-btn ${activePlatform === 'instagram' ? 'active' : ''}`}
                            onClick={() => handlePlatformToggle('instagram')}
                        >
                            <i className="fab fa-instagram"></i> Instagram
                        </button>
                        <button 
                            className={`toggle-btn ${activePlatform === 'linkedin' ? 'active' : ''}`}
                            onClick={() => handlePlatformToggle('linkedin')}
                        >
                            <i className="fab fa-linkedin"></i> LinkedIn
                        </button>
                    </div>
                </div>

                {/* Analytics Dashboard Content */}
                <div className="analytics-dashboard">
                    {/* Facebook Analytics */}
                    <div className={`platform-analytics ${activePlatform === 'facebook' ? 'active' : ''}`} id="facebook-analytics">
                        <div className="facebook-controls">
                            <div className="period-selector">
                                <label htmlFor="facebook-period">Analytics Period:</label>
                                <select 
                                    id="facebook-period" 
                                    onChange={(e) => handlePeriodChange('facebook', parseInt(e.target.value))}
                                    defaultValue="30"
                                >
                                    <option value="7">Last 7 days</option>
                                    <option value="14">Last 14 days</option>
                                    <option value="30">Last 30 days</option>
                                    <option value="60">Last 60 days</option>
                                    <option value="90">Last 90 days</option>
                                </select>
                                <button 
                                    id="refresh-facebook" 
                                    className="refresh-btn-fb"
                                    onClick={() => handlePeriodChange('facebook', parseInt(document.getElementById('facebook-period').value))}
                                    disabled={analyticsLoading}
                                >
                                    <i className={`fas fa-sync-alt ${analyticsLoading ? 'fa-spin' : ''}`}></i> 
                                    {analyticsLoading ? 'Loading...' : 'Refresh'}
                                </button>
                            </div>
                        </div>

                        <div className="analytics-summary">
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-users"></i></div>
                                <div className="metric-info">
                                    <h3 id="fb-total-fans">{formatNumber(analyticsData.facebook?.page_fans)}</h3>
                                    <p>Total Fans</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-eye"></i></div>
                                <div className="metric-info">
                                    <h3 id="fb-total-impressions">{formatNumber(analyticsData.facebook?.page_impressions)}</h3>
                                    <p>Impressions (<span id="fb-period-days">30</span>d)</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-chart-area"></i></div>
                                <div className="metric-info">
                                    <h3 id="fb-total-engagement">{formatNumber(analyticsData.facebook?.page_engagement)}</h3>
                                    <p>Engagement (<span id="fb-engagement-days">30</span>d)</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-chart-line"></i></div>
                                <div className="metric-info">
                                    <h3 id="fb-growth-rate">{analyticsData.facebook?.growth_rate || '--'}%</h3>
                                    <p>Growth Rate</p>
                                </div>
                            </div>
                        </div>

                        <div className="analytics-charts">
                            <div className="chart-container">
                                <h3>Page Fans Growth</h3>
                                <div id="fb-fans-chart-container">
                                    <canvas id="fb-fans-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                            <div className="chart-container">
                                <h3>Impressions vs Engagement</h3>
                                <div id="fb-engagement-chart-container">
                                    <canvas id="fb-engagement-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                            <div className="chart-container">
                                <h3>Reach & Views</h3>
                                <div id="fb-reach-chart-container">
                                    <canvas id="fb-reach-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Instagram Analytics */}
                    <div className={`platform-analytics ${activePlatform === 'instagram' ? 'active' : ''}`} id="instagram-analytics">
                        <div className="instagram-controls">
                            <div className="period-selector">
                                <label htmlFor="instagram-period">Analytics Period:</label>
                                <select 
                                    id="instagram-period" 
                                    onChange={(e) => handlePeriodChange('instagram', parseInt(e.target.value))}
                                    defaultValue="14"
                                >
                                    <option value="7">Last 7 days</option>
                                    <option value="14">Last 14 days</option>
                                    <option value="30">Last 30 days</option>
                                </select>
                                <button 
                                    id="refresh-instagram" 
                                    className="refresh-btn"
                                    onClick={() => handlePeriodChange('instagram', parseInt(document.getElementById('instagram-period').value))}
                                    disabled={analyticsLoading}
                                >
                                    <i className={`fas fa-sync-alt ${analyticsLoading ? 'fa-spin' : ''}`}></i> 
                                    {analyticsLoading ? 'Loading...' : 'Refresh'}
                                </button>
                            </div>
                        </div>

                        <div className="analytics-summary">
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-users"></i></div>
                                <div className="metric-info">
                                    <h3 id="ig-total-followers">{formatNumber(analyticsData.instagram?.followers_count)}</h3>
                                    <p>Total Followers</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-eye"></i></div>
                                <div className="metric-info">
                                    <h3 id="ig-total-views">{formatNumber(analyticsData.instagram?.total_views)}</h3>
                                    <p>Total Views</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-chart-area"></i></div>
                                <div className="metric-info">
                                    <h3 id="ig-accounts-reached">{formatNumber(analyticsData.instagram?.accounts_reached)}</h3>
                                    <p>Accounts Reached</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-chart-line"></i></div>
                                <div className="metric-info">
                                    <h3 id="ig-growth-rate">{analyticsData.instagram?.growth_rate || '--'}%</h3>
                                    <p>Growth Rate</p>
                                </div>
                            </div>
                        </div>

                        {/* Instagram Insights Cards */}
                        <div className="instagram-insights">
                            <div className="insight-card">
                                <h4><i className="fas fa-user-circle"></i> Profile Activity</h4>
                                <div className="insight-stat">
                                    <span className="stat-number" id="ig-profile-views">
                                        {formatNumber(analyticsData.instagram?.profile_views)}
                                    </span>
                                    <span className="stat-label">Profile Views</span>
                                </div>
                            </div>
                            <div className="insight-card">
                                <h4><i className="fas fa-chart-pie"></i> Content Breakdown</h4>
                                <div className="content-stats">
                                    <div className="content-stat">
                                        <span className="content-percentage" id="ig-stories-percent">
                                            {analyticsData.instagram?.content_breakdown?.stories_percentage || '--'}%
                                        </span>
                                        <span className="content-label">Stories</span>
                                    </div>
                                    <div className="content-stat">
                                        <span className="content-percentage" id="ig-posts-percent">
                                            {analyticsData.instagram?.content_breakdown?.posts_percentage || '--'}%
                                        </span>
                                        <span className="content-label">Posts</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="analytics-charts">
                            <div className="chart-container">
                                <h3>Followers Growth Trend</h3>
                                <div id="ig-followers-chart-container">
                                    <canvas id="ig-followers-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                            <div className="chart-container">
                                <h3>Views & Reach</h3>
                                <div id="ig-views-reach-chart-container">
                                    <canvas id="ig-views-reach-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                            <div className="chart-container">
                                <h3>Profile Activity</h3>
                                <div id="ig-profile-activity-chart-container">
                                    <canvas id="ig-profile-activity-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* LinkedIn Analytics */}
                    <div className={`platform-analytics ${activePlatform === 'linkedin' ? 'active' : ''}`} id="linkedin-analytics">
                        <div className="linkedin-controls">
                            <div className="period-selector">
                                <label htmlFor="linkedin-period">Analytics Period:</label>
                                <select 
                                    id="linkedin-period" 
                                    onChange={(e) => handlePeriodChange('linkedin', parseInt(e.target.value))}
                                    defaultValue="30"
                                >
                                    <option value="7">Last 7 days</option>
                                    <option value="14">Last 14 days</option>
                                    <option value="30">Last 30 days</option>
                                    <option value="60">Last 60 days</option>
                                    <option value="90">Last 90 days</option>
                                </select>
                                <button 
                                    id="refresh-linkedin" 
                                    className="refresh-btn-li"
                                    onClick={() => handlePeriodChange('linkedin', parseInt(document.getElementById('linkedin-period').value))}
                                    disabled={analyticsLoading}
                                >
                                    <i className={`fas fa-sync-alt ${analyticsLoading ? 'fa-spin' : ''}`}></i> 
                                    {analyticsLoading ? 'Loading...' : 'Refresh'}
                                </button>
                            </div>
                        </div>

                        <div className="analytics-summary">
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-user-friends"></i></div>
                                <div className="metric-info">
                                    <h3 id="ln-connections">{formatNumber(analyticsData.linkedin?.connections)}</h3>
                                    <p>Total Connections</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-eye"></i></div>
                                <div className="metric-info">
                                    <h3 id="ln-profile-views">{formatNumber(analyticsData.linkedin?.profile_views)}</h3>
                                    <p>Profile Views</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-chart-bar"></i></div>
                                <div className="metric-info">
                                    <h3 id="ln-post-impressions">{formatNumber(analyticsData.linkedin?.post_impressions)}</h3>
                                    <p>Post Impressions</p>
                                </div>
                            </div>
                            <div className="metric-card">
                                <div className="metric-icon"><i className="fas fa-thumbs-up"></i></div>
                                <div className="metric-info">
                                    <h3 id="ln-engagement-rate">{analyticsData.linkedin?.engagement_rate || '--'}%</h3>
                                    <p>Engagement Rate</p>
                                </div>
                            </div>
                        </div>

                        {/* LinkedIn Insights Cards */}
                        <div className="linkedin-insights">
                            <div className="insight-card">
                                <h4><i className="fas fa-chart-line"></i> Network Growth</h4>
                                <div className="insight-stat">
                                    <span className="stat-number" id="ln-growth-rate">
                                        {analyticsData.linkedin?.growth_rate || '--'}%
                                    </span>
                                    <span className="stat-label">Growth Rate</span>
                                </div>
                            </div>
                            <div className="insight-card">
                                <h4><i className="fas fa-industry"></i> Industry Breakdown</h4>
                                <div className="content-stats">
                                    <div className="content-stat">
                                        <span className="content-percentage" id="ln-tech-percent">
                                            {analyticsData.linkedin?.industry_data?.tech || '--'}%
                                        </span>
                                        <span className="content-label">Tech</span>
                                    </div>
                                    <div className="content-stat">
                                        <span className="content-percentage" id="ln-finance-percent">
                                            {analyticsData.linkedin?.industry_data?.finance || '--'}%
                                        </span>
                                        <span className="content-label">Finance</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="analytics-charts">
                            <div className="chart-container">
                                <h3>Connections Growth</h3>
                                <div id="ln-connections-chart-container">
                                    <canvas id="ln-connections-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                            <div className="chart-container">
                                <h3>Profile Views & Impressions</h3>
                                <div id="ln-views-impressions-chart-container">
                                    <canvas id="ln-views-impressions-chart" width="400" height="250"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Dashboard;