/**
 * SSH Session Manager - Modern Web Interface
 * JavaScript application for managing SSH connections
 */

class SSHSessionManager {
    constructor() {
        // State management
        this.hosts = [];
        this.filteredHosts = [];
        this.allTags = [];
        this.currentView = 'grid'; // 'grid' or 'list'
        this.isLoading = false;
        
        // DOM elements
        this.elements = {
            searchBox: document.getElementById('searchBox'),
            tagFilter: document.getElementById('tagFilter'),
            clearSearch: document.getElementById('clearSearch'),
            refreshBtn: document.getElementById('refreshBtn'),
            gridViewBtn: document.getElementById('gridViewBtn'),
            listViewBtn: document.getElementById('listViewBtn'),
            hostCount: document.getElementById('hostCount'),
            loadingState: document.getElementById('loadingState'),
            emptyState: document.getElementById('emptyState'),
            hostsContainer: document.getElementById('hostsContainer'),
            clearFiltersBtn: document.getElementById('clearFiltersBtn'),
            connectionToast: document.getElementById('connectionToast'),
            connectionOverlay: document.getElementById('connectionOverlay')
        };
        
        // Bind event listeners
        this.bindEvents();
        
        // Initialize the application
        this.init();
    }
    
    async init() {
        console.log('Initializing SSH Session Manager...');
        await this.loadHosts();
        await this.loadTags();
        this.renderHosts();
    }
    
    bindEvents() {
        // Search functionality
        this.elements.searchBox.addEventListener('input', 
            this.debounce(() => this.handleSearch(), 300)
        );
        
        // Clear search
        this.elements.clearSearch.addEventListener('click', () => {
            this.elements.searchBox.value = '';
            this.handleSearch();
        });
        
        // Tag filter
        this.elements.tagFilter.addEventListener('change', () => {
            this.handleTagFilter();
        });
        
        // View controls
        this.elements.refreshBtn.addEventListener('click', () => {
            this.refresh();
        });
        
        this.elements.gridViewBtn.addEventListener('click', () => {
            this.setView('grid');
        });
        
        this.elements.listViewBtn.addEventListener('click', () => {
            this.setView('list');
        });
        
        // Clear filters
        this.elements.clearFiltersBtn.addEventListener('click', () => {
            this.clearFilters();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.elements.searchBox.focus();
            }
            
            // Escape to clear search
            if (e.key === 'Escape') {
                this.clearFilters();
            }
            
            // F5 to refresh
            if (e.key === 'F5') {
                e.preventDefault();
                this.refresh();
            }
        });
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    async loadHosts() {
        try {
            this.setLoading(true);
            const response = await fetch('/api/hosts');
            const data = await response.json();
            
            if (data.success) {
                this.hosts = [];
                // Flatten the grouped data
                if (data.data.tag_groups) {
                    for (const [tag, hosts] of Object.entries(data.data.tag_groups)) {
                        this.hosts.push(...hosts);
                    }
                }
                if (data.data.untagged_hosts) {
                    this.hosts.push(...data.data.untagged_hosts);
                }
                
                this.filteredHosts = [...this.hosts];
                this.updateHostCount();
                console.log(`Loaded ${this.hosts.length} hosts`);
            } else {
                throw new Error('Failed to load hosts');
            }
        } catch (error) {
            console.error('Error loading hosts:', error);
            this.showToast('Error loading hosts', 'error');
        } finally {
            this.setLoading(false);
        }
    }
    
    async loadTags() {
        try {
            const response = await fetch('/api/tags');
            const data = await response.json();
            
            if (data.success) {
                this.allTags = data.tags;
                this.populateTagFilter();
                console.log(`Loaded ${this.allTags.length} tags`);
            }
        } catch (error) {
            console.error('Error loading tags:', error);
        }
    }
    
    populateTagFilter() {
        const tagFilter = this.elements.tagFilter;
        // Clear existing options except "All Tags"
        tagFilter.innerHTML = '<option value="">All Tags</option>';
        
        this.allTags.forEach(tag => {
            const option = document.createElement('option');
            option.value = tag;
            option.textContent = tag;
            tagFilter.appendChild(option);
        });
    }
    
    handleSearch() {
        const searchTerm = this.elements.searchBox.value.trim().toLowerCase();
        
        if (searchTerm) {
            this.filteredHosts = this.hosts.filter(host => {
                const searchIn = [
                    host.name,
                    host.hostname,
                    host.username,
                    ...(host.tags || [])
                ].join(' ').toLowerCase();
                
                return searchIn.includes(searchTerm);
            });
            
            // Clear tag filter when searching
            this.elements.tagFilter.value = '';
        } else {
            this.filteredHosts = [...this.hosts];
        }
        
        this.updateHostCount();
        this.renderHosts();
    }
    
    handleTagFilter() {
        const selectedTag = this.elements.tagFilter.value;
        
        if (selectedTag) {
            this.filteredHosts = this.hosts.filter(host => {
                return host.tags && host.tags.includes(selectedTag);
            });
            
            // Clear search when filtering by tag
            this.elements.searchBox.value = '';
        } else {
            this.filteredHosts = [...this.hosts];
        }
        
        this.updateHostCount();
        this.renderHosts();
    }
    
    clearFilters() {
        this.elements.searchBox.value = '';
        this.elements.tagFilter.value = '';
        this.filteredHosts = [...this.hosts];
        this.updateHostCount();
        this.renderHosts();
    }
    
    setView(view) {
        this.currentView = view;
        
        // Update button states
        this.elements.gridViewBtn.classList.toggle('active', view === 'grid');
        this.elements.listViewBtn.classList.toggle('active', view === 'list');
        
        this.renderHosts();
    }
    
    setLoading(loading) {
        this.isLoading = loading;
        
        if (loading) {
            this.elements.loadingState.style.display = 'flex';
            this.elements.emptyState.style.display = 'none';
            this.elements.hostsContainer.style.display = 'none';
        } else {
            this.elements.loadingState.style.display = 'none';
        }
        
        // Update refresh button
        if (this.elements.refreshBtn) {
            const icon = this.elements.refreshBtn.querySelector('i');
            if (loading) {
                icon.classList.add('fa-spin');
            } else {
                icon.classList.remove('fa-spin');
            }
        }
    }
    
    updateHostCount() {
        const total = this.hosts.length;
        const filtered = this.filteredHosts.length;
        
        if (filtered === total) {
            this.elements.hostCount.textContent = `${total} host${total !== 1 ? 's' : ''}`;
        } else {
            this.elements.hostCount.textContent = `${filtered} of ${total} hosts`;
        }
    }
    
    renderHosts() {
        if (this.isLoading) return;
        
        if (this.filteredHosts.length === 0) {
            this.elements.emptyState.style.display = 'flex';
            this.elements.hostsContainer.style.display = 'none';
            return;
        }
        
        this.elements.emptyState.style.display = 'none';
        this.elements.hostsContainer.style.display = 'block';
        
        // Group hosts by tags
        const grouped = this.groupHostsByTags(this.filteredHosts);
        
        // Generate HTML
        const html = this.generateHostsHTML(grouped);
        this.elements.hostsContainer.innerHTML = html;
        
        // Bind click events to host tiles
        this.bindHostClickEvents();
    }
    
    groupHostsByTags(hosts) {
        const tagGroups = {};
        const untaggedHosts = [];
        
        hosts.forEach(host => {
            const hostTags = host.tags || [];
            if (hostTags.length === 0) {
                untaggedHosts.push(host);
            } else {
                const primaryTag = hostTags[0];
                if (!tagGroups[primaryTag]) {
                    tagGroups[primaryTag] = [];
                }
                tagGroups[primaryTag].push(host);
            }
        });
        
        return { tagGroups, untaggedHosts };
    }
    
    generateHostsHTML(grouped) {
        let html = '';
        
        // Add tagged groups
        const sortedTags = Object.keys(grouped.tagGroups).sort();
        for (const tag of sortedTags) {
            const hosts = grouped.tagGroups[tag];
            const tagClass = this.getTagClass(tag);
            
            html += `
                <div class="host-group">
                    <div class="group-header ${tagClass}">
                        <i class="fas fa-folder"></i>
                        ${tag.toUpperCase()}
                        <span class="host-count-badge">${hosts.length}</span>
                    </div>
                    <div class="${this.currentView === 'grid' ? 'hosts-grid' : 'hosts-list'}">
                        ${hosts.map(host => this.generateHostTileHTML(host, tag)).join('')}
                    </div>
                </div>
            `;
        }
        
        // Add untagged hosts
        if (grouped.untaggedHosts.length > 0) {
            html += `
                <div class="host-group">
                    <div class="group-header tag-untagged">
                        <i class="fas fa-file"></i>
                        UNTAGGED
                        <span class="host-count-badge">${grouped.untaggedHosts.length}</span>
                    </div>
                    <div class="${this.currentView === 'grid' ? 'hosts-grid' : 'hosts-list'}">
                        ${grouped.untaggedHosts.map(host => this.generateHostTileHTML(host, 'untagged')).join('')}
                    </div>
                </div>
            `;
        }
        
        return html;
    }
    
    generateHostTileHTML(host, primaryTag) {
        const authIcon = host.auth_method === 'key' ? 'fas fa-key' : 'fas fa-lock';
        const tagClass = this.getTagClass(primaryTag);
        const tagsText = host.tags && host.tags.length > 0 ? host.tags.join(', ') : 'NO TAGS';
        const viewClass = this.currentView === 'list' ? 'list-view' : '';
        const tagColor = this.getTagColor(primaryTag);
        
        return `
            <div class="host-tile ${tagClass} ${viewClass}" data-host-name="${host.name}">
                <div class="host-name">${host.name}</div>
                <div class="host-connection">${host.username}@${host.hostname}:${host.port}</div>
                <div class="host-details">
                    <div class="auth-icon">
                        <i class="${authIcon}" title="${host.auth_method === 'key' ? 'SSH Key Authentication' : 'Password Authentication'}"></i>
                    </div>
                    <div class="host-tags" style="background-color: ${tagColor}; color: white;">${tagsText}</div>
                </div>
            </div>
        `;
    }
    
    getTagClass(tag) {
        const tagLower = tag.toLowerCase();
        
        if (['production', 'prod'].includes(tagLower)) return 'tag-production';
        if (['staging', 'stage'].includes(tagLower)) return 'tag-staging';
        if (['development', 'dev'].includes(tagLower)) return 'tag-development';
        if (['testing', 'test'].includes(tagLower)) return 'tag-testing';
        if (['database', 'db'].includes(tagLower)) return 'tag-database';
        if (tagLower === 'web') return 'tag-web';
        if (tagLower === 'api') return 'tag-api';
        if (tagLower === 'untagged') return 'tag-untagged';
        
        return 'tag-default';
    }
    
    getTagColor(tag) {
        const tagLower = tag.toLowerCase();
        
        if (['production', 'prod'].includes(tagLower)) return '#dc3545';
        if (['staging', 'stage'].includes(tagLower)) return '#fd7e14';
        if (['development', 'dev'].includes(tagLower)) return '#198754';
        if (['testing', 'test'].includes(tagLower)) return '#6f42c1';
        if (['database', 'db'].includes(tagLower)) return '#0dcaf0';
        if (tagLower === 'web') return '#0d6efd';
        if (tagLower === 'api') return '#6610f2';
        if (tagLower === 'untagged') return '#6c757d';
        
        return '#6c757d'; // default gray
    }
    
    bindHostClickEvents() {
        const hostTiles = document.querySelectorAll('.host-tile');
        hostTiles.forEach(tile => {
            tile.addEventListener('click', () => {
                const hostName = tile.dataset.hostName;
                this.connectToHost(hostName);
            });
            
            // Add keyboard support
            tile.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const hostName = tile.dataset.hostName;
                    this.connectToHost(hostName);
                }
            });
            
            // Make tiles focusable
            tile.setAttribute('tabindex', '0');
        });
    }
    
    async connectToHost(hostName) {
        try {
            console.log(`Connecting to host: ${hostName}`);
            
            // Find host details
            const host = this.hosts.find(h => h.name === hostName);
            if (!host) {
                throw new Error(`Host "${hostName}" not found`);
            }
            
            // Show connection overlay
            this.showConnectionOverlay(host);
            
            const response = await fetch('/api/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ host_name: hostName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`SSH session launched for ${hostName}`, 'success');
                console.log('Connection successful:', data);
            } else {
                throw new Error(data.detail || 'Connection failed');
            }
            
        } catch (error) {
            console.error('Connection error:', error);
            this.showToast(`Connection failed: ${error.message}`, 'error');
        } finally {
            // Hide connection overlay after a delay
            setTimeout(() => {
                this.hideConnectionOverlay();
            }, 2000);
        }
    }
    
    showConnectionOverlay(host) {
        const overlay = this.elements.connectionOverlay;
        const hostElement = overlay.querySelector('.connection-host');
        
        if (hostElement) {
            hostElement.textContent = `${host.username}@${host.hostname}:${host.port}`;
        }
        
        overlay.classList.add('show');
    }
    
    hideConnectionOverlay() {
        this.elements.connectionOverlay.classList.remove('show');
    }
    
    showToast(message, type = 'info') {
        const toast = this.elements.connectionToast;
        const icon = toast.querySelector('.toast-icon');
        const title = toast.querySelector('.toast-title');
        const messageEl = toast.querySelector('.toast-message');
        
        // Clear previous classes
        toast.className = 'connection-toast';
        
        // Set content based on type
        switch (type) {
            case 'success':
                toast.classList.add('toast-success');
                icon.className = 'toast-icon fas fa-check-circle';
                title.textContent = 'Connection Successful';
                break;
            case 'error':
                toast.classList.add('toast-error');
                icon.className = 'toast-icon fas fa-exclamation-circle';
                title.textContent = 'Connection Failed';
                break;
            default:
                toast.classList.add('toast-info');
                icon.className = 'toast-icon fas fa-info-circle';
                title.textContent = 'Information';
        }
        
        messageEl.textContent = message;
        
        // Show toast
        toast.classList.add('show');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
        }, 5000);
    }
    
    async refresh() {
        console.log('Refreshing hosts...');
        await this.loadHosts();
        await this.loadTags();
        this.renderHosts();
        this.showToast('Hosts refreshed successfully', 'success');
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing SSH Session Manager...');
    window.sshManager = new SSHSessionManager();
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    event.preventDefault();
});
