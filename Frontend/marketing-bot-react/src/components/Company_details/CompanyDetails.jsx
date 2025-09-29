import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AuthContext } from '../../services/AuthContext';
import './CompanyDetails.css';
import logo from "../../assets/imgs/logo/logo.png";

const CompanyDetails = () => {
    const { companyId } = useParams();
    const navigate = useNavigate();
    const { user, token } = useContext(AuthContext);
    const [companyData, setCompanyData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        fetchCompanyDetails();
    }, [companyId]);

    const fetchCompanyDetails = async () => {
        try {
            const response = await fetch(`http://localhost:8000/api/company/${companyId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch company details');
            }

            const data = await response.json();
            setCompanyData(data);
        } catch (err) {
            setError('Error loading company details');
            console.error('Error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteCompany = async () => {
        if (window.confirm('Are you sure? This will delete all associated strategies too.')) {
            try {
                const response = await fetch(`http://localhost:8000/api/company/${companyId}`, {
                    method: 'DELETE',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (response.ok) {
                    navigate('/home');
                } else {
                    throw new Error('Failed to delete company');
                }
            } catch (err) {
                setError('Error deleting company');
                console.error('Error:', err);
            }
        }
    };

    const formatWebsite = (website) => {
        if (!website || website === "Not provided") return null;
        const url = website.startsWith('http') ? website : `http://${website}`;
        return (
            <a href={url} target="_blank" rel="noopener noreferrer" className="website-link">
                {website} <i className="fas fa-external-link-alt"></i>
            </a>
        );
    };

    const formatPhone = (phone) => {
        if (!phone || phone === "Not provided") return null;
        return (
            <a href={`https://wa.me/${phone}`} target="_blank" className="whatsapp-link">
                {phone} <i className="fab fa-whatsapp"></i>
            </a>
        );
    };

    const renderTags = (tagsString, tagClass = 'tag') => {
        if (!tagsString || tagsString === "Not provided") return "Not provided";
        
        const tags = tagsString.split(',').map(tag => tag.trim()).filter(tag => tag);
        return (
            <div className="tags-container">
                {tags.map((tag, index) => (
                    <span key={index} className={`tag ${tagClass}`}>{tag}</span>
                ))}
            </div>
        );
    };

    const renderTargetAudience = (company) => {
        const parts = [];
        if (company.target_age_groups) parts.push(`Age Groups: ${company.target_age_groups}`);
        if (company.target_audience_types) parts.push(`Types: ${company.target_audience_types}`);
        if (company.target_business_types) parts.push(`Businesses: ${company.target_business_types}`);
        if (company.target_geographics) parts.push(`Geographics: ${company.target_geographics}`);

        if (parts.length === 0) return "Not specified";

        return (
            <div className="audience-details">
                {parts.map((part, index) => (
                    <div key={index} className="audience-section">
                        <strong>{part.split(':')[0]}:</strong>
                        <div className="tags-container">
                            {part.split(':')[1].split(',').map((item, idx) => (
                                item.trim() && <span key={idx} className="tag audience-tag">{item.trim()}</span>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    if (loading) return <div className="loading">Loading company details...</div>;
    if (error) return <div className="error">{error}</div>;
    if (!companyData) return <div className="error">Company not found</div>;

    const { company, approved_strategy, strategy_counts } = companyData;

    return (
        <div>
            {/* Top Navigation Bar */}
            <nav className="top-nav">
                <div className="nav-container">
                    <div className="nav-left">
                        <button className="sidebar-toggle">
                            <i className="fas fa-bars"></i>
                        </button>
                        <Link to="/" target="_blank" className="logo">
                            <img src={logo} alt="Chahbender" className="logo-img" />
                        </Link>
                    </div>
                    <div className="nav-right">
                        <div className="user-menu">
                            <div className="user-avatar" data-name={user.full_name} id="userAvatar" title={user.full_name}>
                                {user.full_name[0]}
                            </div>
                            <div className="dropdown-menu" id="dropdownMenu">
                                <Link to="/home" className="dropdown-item">
                                    <i className="fas fa-user"></i> {user.full_name}
                                </Link>
                                <Link to="/user_settings" className="dropdown-item">
                                    <i className="fas fa-cog"></i> User Settings
                                </Link>
                                <Link to="/logout" className="dropdown-item logout">
                                    <i className="fas fa-sign-out-alt"></i> Logout
                                </Link>
                            </div>
                        </div>
                    </div>
                </div>
            </nav>

            {/* Sidebar */}
            <aside className="sidebar">
                <ul className="sidebar-menu">
                    <li><Link to="/home" className="nav-link"><i className="fas fa-home"></i> Home</Link></li>
                    <li><a href="#company-profile" className="active"><i className="fas fa-building"></i> Company Profile</a></li>
                    <li><Link to={`/edit_company/${company.id}`} className=""><i className="fas fa-edit"></i> Edit Profile</Link></li>
                    <li><a href="#Strategies" className=""><i className="fas fa-lightbulb"></i> Generated Strategy</a></li>
                    <li><Link to="/user_settings" className=""><i className="fas fa-cog"></i> User Settings</Link></li>
                    <li><Link to="/logout" className="nav-link-logout"><i className="fas fa-sign-out-alt"></i> Logout</Link></li>
                </ul>
            </aside>

            <br /><br />

            {/* Main Content */}
            <main className="main-content" id="company-profile">
                <div className="company-info" id="company-profile">
                    <div className="company-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h2><i className="fas fa-building"></i> Company Profile</h2>
                        <div className="company-actions">
                            <button onClick={handleDeleteCompany} className="btn-remove-profile">
                                <i className="fas fa-trash"></i> Delete Profile
                            </button>
                        </div>
                    </div>

                    {/* Company Information Grid */}
                    <div className="info-grid">
                        {/* Company Information Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-signature"></i> Company Information</h4>
                            {company.logo_url && (
                                <div className="company-logo-container">
                                    <img src={company.logo_url} alt={`${company.name} Logo`} className="company-profile-logo" />
                                </div>
                            )}
                            <p><strong>Name:</strong> {company.name}</p>
                            <p><strong>Website:</strong> {formatWebsite(company.website) || "Not provided"}</p>
                            <p><strong>Phone Number:</strong> {formatPhone(company.phone_number) || "Not provided"}</p>
                        </div>

                        {/* Brand Identity Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-quote-left"></i> Brand Identity</h4>
                            <p><strong>Slogan:</strong> {company.slogan}</p>
                            <p><strong>Description:</strong> {company.description}</p>
                            <p><strong>Brand Tone:</strong> {company.brand_tone}</p>
                        </div>

                        {/* Products & Services Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-boxes"></i> Products & Services</h4>
                            <p><strong>Products:</strong> {renderTags(company.products, 'product-tag')}</p>
                            <p><strong>Services:</strong> {renderTags(company.services, 'service-tag')}</p>
                        </div>

                        {/* Marketing Details Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-bullseye"></i> Marketing Details</h4>
                            <p><strong>Marketing Goals:</strong> {renderTags(company.marketing_goals, 'goal-tag')}</p>
                            <p><strong>Monthly Budget:</strong> 
                                {company.monthly_budget && company.monthly_budget !== "Not specified" ? (
                                    <span className="tag budget-tag"> {company.monthly_budget} TND</span>
                                ) : "Not provided"}
                            </p>
                            <p><strong>Challenges:</strong> {renderTags(company.marketing_challenges, 'challenge-tag')}</p>
                        </div>

                        {/* Target Audience Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-users"></i> Target Audience</h4>
                            {renderTargetAudience(company)}
                        </div>

                        {/* Geographic Targeting Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-globe"></i> Geographic Targeting</h4>
                            {company.target_geographics ? (
                                <div className="tags-container">
                                    {company.target_geographics.split(',').map((geo, index) => (
                                        geo.trim() && <span key={index} className="tag geo-tag">{geo.trim()}</span>
                                    ))}
                                </div>
                            ) : "Not specified"}
                        </div>

                        {/* Platforms Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-share-alt"></i> Platforms</h4>
                            {renderTags(company.preferred_platforms, 'platform-tag')}
                        </div>

                        {/* Special Events Card */}
                        <div className="info-card">
                            <h4><i className="fas fa-calendar-alt"></i> Special Events</h4>
                            {renderTags(company.special_events, 'event-tag')}
                        </div>
                    </div>

                    <hr />
                    <br />

                    {/* Strategies Section */}
                    <div className="strategies-header" id="strategies">
                        <h2><i className="fas fa-chart-line"></i> Generated Strategy</h2>
                        <Link to={`/strategy/new/${company.id}`} className="btn btn-primary">
                            <i className="fas fa-magic"></i> Generate New Strategy With Chahbander
                        </Link>
                    </div>

                    {/* Strategy Stats */}
                    {strategy_counts && (
                        <div className="strategy-stats">
                            <div className="stats-container">
                                <div className="stat-box">
                                    <span className="stat-number">{strategy_counts.total}</span>
                                    <span className="stat-label">Generated</span>
                                </div>
                                <div className="stat-box approved">
                                    <span className="stat-number">{strategy_counts.approved}</span>
                                    <span className="stat-label">Approved</span>
                                </div>
                                <div className="stat-box archived">
                                    <span className="stat-number">{strategy_counts.archived}</span>
                                    <span className="stat-label">Archived</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Approved Strategy Section */}
                    {approved_strategy && (
                        <div className="approved-strategy-section" id="approved-strategy">
                            <div className="section-header">
                                <h3><i className="fas fa-check-circle"></i> Approved Strategy</h3>
                                <span className="badge approved-badge">ACTIVE</span>
                            </div>
                            <div className="strategy-card approved">
                                <div className="strategy-header">
                                    <h4><i className="fas fa-calendar-day"></i> {approved_strategy.created_at}</h4>
                                    <div className="strategy-preview">
                                        {approved_strategy.content.substring(0, 300)}...
                                    </div>
                                </div>
                                <br />
                                <div className="strategy-actions">
                                    <Link to={`/launch_strategy/${approved_strategy.id}`} className="btn btn-launch" target="_blank">
                                        <i className="fas fa-rocket"></i> Launch Strategy
                                    </Link>
                                    <Link to={`/strategy/${approved_strategy.id}`} className="btn btn-primary">
                                        <i className="fas fa-eye"></i> View
                                    </Link>
                                    <Link to={`/edit_strategy/${approved_strategy.id}`} className="btn btn-secondary">
                                        <i className="fas fa-edit"></i> Edit
                                    </Link>
                                    <button className="btn btn-danger" onClick={() => window.confirm('Delete this strategy?')}>
                                        <i className="fas fa-trash"></i> Delete
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>

            {/* Include the same JavaScript */}
            <script src="/static/js/CompanyDetails.js"></script>
        </div>
    );
};

export default CompanyDetails;