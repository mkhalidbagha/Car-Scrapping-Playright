# main.py - Updated FastAPI application with real scrapers
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import json
import csv
import os
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd
import threading
import concurrent.futures

# Import the scraper integration module
try:
    from scraper_integration import (
        scrape_classic_valuer_background,
        scrape_classic_com_background,
        CLASSIC_VALUER_DEFAULT_OPTIONS,
        CLASSIC_COM_DEFAULT_OPTIONS
    )
    SCRAPERS_AVAILABLE = True
except ImportError:
    print("⚠️ Scraper integration module not found. Using simulation mode.")
    SCRAPERS_AVAILABLE = False

app = FastAPI(
    title="Car Auction Scraper API", 
    description="Web scraper for classic car auction data from multiple sources",
    version="2.0.0"
)

# Global storage for scraping jobs
scraping_jobs = {}

class ScrapingRequest(BaseModel):
    scraper_type: str  # "classic_valuer" or "classic_com"
    options: Optional[Dict] = {}

class ScrapingStatus(BaseModel):
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    message: str
    progress: Optional[int] = 0
    total_records: Optional[int] = 0
    results: Optional[List[Dict]] = []
    csv_file: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

# Fallback simulation functions for when real scrapers aren't available
async def simulate_classic_valuer_scraper(options: Dict = None):
    """Simulation of Classic Valuer scraper"""
    await asyncio.sleep(5)  # Simulate work
    return {
        'success': True,
        'records_found': 12,
        'csv_file': f'classic_valuer_sim_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        'results': [
            {'make': 'Ferrari', 'model': '250 GT', 'production_year': '1962', 'sold_price': '£2,500,000', 'date_of_sale': '15/07/2024'},
            {'make': 'Porsche', 'model': '911 Turbo', 'production_year': '1975', 'sold_price': '£150,000', 'date_of_sale': '20/07/2024'},
            {'make': 'Aston Martin', 'model': 'DB5', 'production_year': '1964', 'sold_price': '£800,000', 'date_of_sale': '22/07/2024'},
        ]
    }

def simulate_classic_com_scraper(options: Dict = None):
    """Simulation of Classic.com scraper"""
    import time
    time.sleep(4)  # Simulate work
    results = [
        {'Make': 'Jaguar', 'Model': 'E-Type', 'Production Year': '1961', 'Sold Price': '£120,000', 'Date of Sale': '18/07/2024'},
        {'Make': 'Mercedes-Benz', 'Model': '300SL', 'Production Year': '1955', 'Sold Price': '£1,200,000', 'Date of Sale': '25/07/2024'},
        {'Make': 'BMW', 'Model': '2002 Turbo', 'Production Year': '1974', 'Sold Price': '£85,000', 'Date of Sale': '28/07/2024'},
    ]
    
    # Create simulation CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'classic_com_sim_{timestamp}.csv'
    df = pd.DataFrame(results)
    df.to_csv(csv_filename, index=False)
    
    return {
        'success': True,
        'records_found': len(results),
        'csv_file': csv_filename,
        'results': results
    }

async def run_classic_valuer_background(job_id: str, options: Dict):
    """Background task for Classic Valuer scraping"""
    try:
        scraping_jobs[job_id]['status'] = 'running'
        scraping_jobs[job_id]['message'] = 'Initializing Classic Valuer scraper...'
        scraping_jobs[job_id]['progress'] = 10
        
        if SCRAPERS_AVAILABLE:
            # Use real scraper
            await scrape_classic_valuer_background(job_id, options, scraping_jobs)
        else:
            # Use simulation
            scraping_jobs[job_id]['progress'] = 25
            scraping_jobs[job_id]['message'] = 'Running simulation (real scrapers not available)...'
            
            result = await simulate_classic_valuer_scraper(options)
            
            scraping_jobs[job_id]['progress'] = 75
            scraping_jobs[job_id]['message'] = 'Processing simulated results...'
            
            if result['success']:
                scraping_jobs[job_id]['status'] = 'completed'
                scraping_jobs[job_id]['message'] = f'Simulation completed: {result["records_found"]} records'
                scraping_jobs[job_id]['total_records'] = result['records_found']
                scraping_jobs[job_id]['results'] = result.get('results', [])
                scraping_jobs[job_id]['csv_file'] = result.get('csv_file')
                scraping_jobs[job_id]['progress'] = 100
            else:
                scraping_jobs[job_id]['status'] = 'failed'
                scraping_jobs[job_id]['message'] = f'Simulation failed: {result.get("error", "Unknown error")}'
            
            scraping_jobs[job_id]['completed_at'] = datetime.now().isoformat()
            
    except Exception as e:
        scraping_jobs[job_id]['status'] = 'failed'
        scraping_jobs[job_id]['message'] = f'Error: {str(e)}'
        scraping_jobs[job_id]['completed_at'] = datetime.now().isoformat()

def run_classic_com_background(job_id: str, options: Dict):
    """Background task for Classic.com scraping"""
    try:
        scraping_jobs[job_id]['status'] = 'running'
        scraping_jobs[job_id]['message'] = 'Initializing Classic.com scraper...'
        scraping_jobs[job_id]['progress'] = 10
        
        if SCRAPERS_AVAILABLE:
            # Use real scraper
            scrape_classic_com_background(job_id, options, scraping_jobs)
        else:
            # Use simulation
            scraping_jobs[job_id]['progress'] = 30
            scraping_jobs[job_id]['message'] = 'Running simulation (real scrapers not available)...'
            
            result = simulate_classic_com_scraper(options)
            
            scraping_jobs[job_id]['progress'] = 80
            scraping_jobs[job_id]['message'] = 'Processing simulated results...'
            
            if result['success']:
                scraping_jobs[job_id]['status'] = 'completed'
                scraping_jobs[job_id]['message'] = f'Simulation completed: {result["records_found"]} records'
                scraping_jobs[job_id]['total_records'] = result['records_found']
                scraping_jobs[job_id]['results'] = result['results'][:10] if result['results'] else []
                scraping_jobs[job_id]['csv_file'] = result.get('csv_file')
                scraping_jobs[job_id]['progress'] = 100
            else:
                scraping_jobs[job_id]['status'] = 'failed'
                scraping_jobs[job_id]['message'] = f'Simulation failed: {result.get("error", "Unknown error")}'
            
            scraping_jobs[job_id]['completed_at'] = datetime.now().isoformat()
            
    except Exception as e:
        scraping_jobs[job_id]['status'] = 'failed'
        scraping_jobs[job_id]['message'] = f'Error: {str(e)}'
        scraping_jobs[job_id]['completed_at'] = datetime.now().isoformat()

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard HTML page"""
    scraper_status = "🟢 Real Scrapers Available" if SCRAPERS_AVAILABLE else "🟡 Simulation Mode"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Car Auction Scraper Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{ 
                max-width: 1400px; 
                margin: 0 auto; 
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
            .header p {{ font-size: 1.1em; opacity: 0.9; }}
            .status-banner {{
                background: {'#28a745' if SCRAPERS_AVAILABLE else '#ffc107'};
                color: {'white' if SCRAPERS_AVAILABLE else '#212529'};
                padding: 10px;
                text-align: center;
                font-weight: 600;
            }}
            .content {{ padding: 30px; }}
            .scraper-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 25px;
                margin-bottom: 30px;
            }}
            .scraper-section {{
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
                border-left: 5px solid #667eea;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }}
            .scraper-section:hover {{
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            }}
            .scraper-section h2 {{ 
                color: #333; 
                margin-bottom: 15px;
                font-size: 1.5em;
            }}
            .scraper-section p {{ 
                color: #666; 
                margin-bottom: 20px;
                line-height: 1.6;
            }}
            .scraper-options {{
                background: white;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 20px;
                border: 1px solid #e9ecef;
            }}
            .option-group {{
                margin-bottom: 15px;
            }}
            .option-group label {{
                display: block;
                margin-bottom: 5px;
                font-weight: 600;
                color: #333;
            }}
            .option-group input, .option-group select {{
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
            }}
            .btn {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 25px;
                cursor: pointer;
                font-size: 1em;
                font-weight: 600;
                transition: all 0.3s ease;
                display: inline-block;
                text-decoration: none;
                width: 100%;
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }}
            .btn:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }}
            .status-section {{
                background: white;
                border: 2px solid #e9ecef;
                border-radius: 15px;
                padding: 25px;
                margin-top: 25px;
            }}
            .progress-bar {{
                width: 100%;
                height: 10px;
                background: #e9ecef;
                border-radius: 5px;
                overflow: hidden;
                margin: 15px 0;
            }}
            .progress-fill {{
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                border-radius: 5px;
                transition: width 0.3s ease;
            }}
            .results-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            .results-table th {{
                background: #667eea;
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
            }}
            .results-table td {{
                padding: 12px 15px;
                border-bottom: 1px solid #e9ecef;
            }}
            .results-table tr:nth-child(even) {{
                background: #f8f9fa;
            }}
            .status-badge {{
                padding: 5px 12px;
                border-radius: 15px;
                font-size: 0.9em;
                font-weight: 600;
                text-transform: uppercase;
            }}
            .status-pending {{ background: #fff3cd; color: #856404; }}
            .status-running {{ background: #d1ecf1; color: #0c5460; }}
            .status-completed {{ background: #d4edda; color: #155724; }}
            .status-failed {{ background: #f8d7da; color: #721c24; }}
            .job-card {{
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 15px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            .download-link {{
                color: #667eea;
                text-decoration: none;
                font-weight: 600;
            }}
            .download-link:hover {{
                text-decoration: underline;
            }}
            @media (max-width: 768px) {{
                .scraper-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚗 Car Auction Scraper</h1>
                <p>Scrape classic car auction data from multiple sources</p>
            </div>
            
            <div class="status-banner">
                {scraper_status}
            </div>
            
            <div class="content">
                <div class="scraper-grid">
                    <div class="scraper-section">
                        <h2>🏛️ The Classic Valuer</h2>
                        <p>Scrape market data from TheClassicValuer.com including sold prices, auction houses, and vehicle details.</p>
                        
                        <div class="scraper-options">
                            <h4>Options:</h4>
                            <div class="option-group">
                                <label>Max Pages:</label>
                                <input type="number" id="cv-max-pages" value="3" min="1" max="10">
                            </div>
                            <div class="option-group">
                                <label>Headless Mode:</label>
                                <select id="cv-headless">
                                    <option value="true">Yes (Faster)</option>
                                    <option value="false">No (Debug)</option>
                                </select>
                            </div>
                            <div class="option-group">
                                <label>Delay (ms):</label>
                                <input type="number" id="cv-delay" value="3000" min="1000" max="10000" step="1000">
                            </div>
                        </div>
                        
                        <button class="btn" onclick="startScraping('classic_valuer')">Start Classic Valuer Scraping</button>
                    </div>
                    
                    <div class="scraper-section">
                        <h2>🔗 Classic.com</h2>
                        <p>Extract auction listings from Classic.com with detailed vehicle information and pricing data.</p>
                        
                        <div class="scraper-options">
                            <h4>Options:</h4>
                            <div class="option-group">
                                <label>Search Page:</label>
                                <input type="number" id="cc-page" value="1" min="1" max="50">
                            </div>
                            <div class="option-group">
                                <label>Max Listings:</label>
                                <input type="number" id="cc-max-listings" value="50" min="1" max="200">
                            </div>
                            <div class="option-group">
                                <label>USD to GBP Rate:</label>
                                <input type="number" id="cc-conversion" value="0.76" min="0.5" max="1.0" step="0.01">
                            </div>
                        </div>
                        
                        <button class="btn" onclick="startScraping('classic_com')">Start Classic.com Scraping</button>
                    </div>
                </div>
                
                <div class="status-section">
                    <h2>📊 Scraping Status & Results</h2>
                    <div id="jobs-container">
                        <p>No active scraping jobs. Start a scraper above to see progress here.</p>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let activeJobs = new Set();
            
            async function startScraping(scraperType) {{
                try {{
                    let options = {{}};
                    
                    if (scraperType === 'classic_valuer') {{
                        options = {{
                            max_pages: parseInt(document.getElementById('cv-max-pages').value),
                            headless: document.getElementById('cv-headless').value === 'true',
                            delay: parseInt(document.getElementById('cv-delay').value)
                        }};
                    }} else if (scraperType === 'classic_com') {{
                        options = {{
                            page: parseInt(document.getElementById('cc-page').value),
                            max_listings: parseInt(document.getElementById('cc-max-listings').value),
                            conversion_rate: parseFloat(document.getElementById('cc-conversion').value)
                        }};
                    }}
                    
                    const response = await fetch('/scrape', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ 
                            scraper_type: scraperType,
                            options: options
                        }})
                    }});
                    
                    const result = await response.json();
                    if (result.job_id) {{
                        activeJobs.add(result.job_id);
                        pollJobStatus(result.job_id);
                        showNotification(`Started ${{scraperType}} scraping`, 'success');
                    }}
                }} catch (error) {{
                    showNotification('Failed to start scraping', 'error');
                }}
            }}
            
            async function pollJobStatus(jobId) {{
                const pollInterval = setInterval(async () => {{
                    try {{
                        const response = await fetch(`/status/${{jobId}}`);
                        const status = await response.json();
                        
                        updateJobDisplay(status);
                        
                        if (status.status === 'completed' || status.status === 'failed') {{
                            clearInterval(pollInterval);
                            activeJobs.delete(jobId);
                            
                            if (status.status === 'completed') {{
                                showNotification(`Scraping completed! Found ${{status.total_records}} records`, 'success');
                            }} else {{
                                showNotification('Scraping failed', 'error');
                            }}
                        }}
                    }} catch (error) {{
                        clearInterval(pollInterval);
                        activeJobs.delete(jobId);
                    }}
                }}, 2000);
            }}
            
            function updateJobDisplay(status) {{
                const container = document.getElementById('jobs-container');
                let jobCard = document.getElementById(`job-${{status.job_id}}`);
                
                if (!jobCard) {{
                    if (container.children.length === 1 && container.children[0].tagName === 'P') {{
                        container.innerHTML = '';
                    }}
                    jobCard = document.createElement('div');
                    jobCard.id = `job-${{status.job_id}}`;
                    jobCard.className = 'job-card';
                    container.appendChild(jobCard);
                }}
                
                jobCard.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <h3>Job: ${{status.job_id}}</h3>
                        <span class="status-badge status-${{status.status}}">${{status.status}}</span>
                    </div>
                    <p><strong>Message:</strong> ${{status.message}}</p>
                    ${{status.progress !== null ? `
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${{status.progress}}%"></div>
                        </div>
                        <p><small>Progress: ${{status.progress}}%</small></p>
                    ` : ''}}
                    ${{status.total_records ? `<p><strong>Records Found:</strong> ${{status.total_records}}</p>` : ''}}
                    ${{status.csv_file ? `<p><strong>CSV File:</strong> <a href="/download/${{status.csv_file}}" download class="download-link">${{status.csv_file}}</a></p>` : ''}}
                    ${{status.results && status.results.length > 0 ? `
                        <h4 style="margin-top: 20px;">Sample Results (First 5):</h4>
                        <table class="results-table">
                            <thead>
                                <tr>
                                    ${{Object.keys(status.results[0]).map(key => `<th>${{key}}</th>`).join('')}}
                                </tr>
                            </thead>
                            <tbody>
                                ${{status.results.slice(0, 5).map(result => `
                                    <tr>
                                        ${{Object.values(result).map(value => `<td>${{value}}</td>`).join('')}}
                                    </tr>
                                `).join('')}}
                            </tbody>
                        </table>
                        ${{status.total_records > 5 ? `
                            <p style="margin-top: 10px; color: #666;"><em>Showing 5 of ${{status.total_records}} records. Download CSV for complete data.</em></p>
                        ` : ''}}
                    ` : ''}}
                    ${{status.status === 'completed' ? `
                        <div style="margin-top: 20px;">
                            <button class="btn" onclick="viewFullResults('${{status.job_id}}')" style="width: auto; margin-right: 10px;">View All Results</button>
                            <button class="btn" onclick="deleteJob('${{status.job_id}}')" style="width: auto; background: #dc3545;">Delete Job</button>
                        </div>
                    ` : ''}}
                `;
            }}
            
            async function viewFullResults(jobId) {{
                try {{
                    const response = await fetch(`/results/${{jobId}}`);
                    const data = await response.json();
                    
                    // Create a modal or new window to show all results
                    const modal = document.createElement('div');
                    modal.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.8);
                        z-index: 1000;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    `;
                    
                    const modalContent = document.createElement('div');
                    modalContent.style.cssText = `
                        background: white;
                        border-radius: 15px;
                        padding: 30px;
                        max-width: 90%;
                        max-height: 90%;
                        overflow: auto;
                        position: relative;
                    `;
                    
                    modalContent.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                            <h2>Full Results - Job ${{jobId}}</h2>
                            <button onclick="this.closest('div').parentElement.remove()" style="background: #dc3545; color: white; border: none; padding: 8px 12px; border-radius: 5px; cursor: pointer;">Close</button>
                        </div>
                        <p><strong>Total Records:</strong> ${{data.total_records}}</p>
                        <div style="max-height: 60vh; overflow: auto; margin-top: 20px;">
                            <table class="results-table" style="font-size: 12px;">
                                <thead>
                                    <tr>
                                        ${{data.data && data.data.length > 0 ? Object.keys(data.data[0]).map(key => `<th>${{key}}</th>`).join('') : ''}}
                                    </tr>
                                </thead>
                                <tbody>
                                    ${{data.data ? data.data.map(result => `
                                        <tr>
                                            ${{Object.values(result).map(value => `<td>${{value}}</td>`).join('')}}
                                        </tr>
                                    `).join('') : ''}}
                                </tbody>
                            </table>
                        </div>
                    `;
                    
                    modal.appendChild(modalContent);
                    document.body.appendChild(modal);
                    
                }} catch (error) {{
                    showNotification('Failed to load full results', 'error');
                }}
            }}
            
            async function deleteJob(jobId) {{
                if (confirm('Are you sure you want to delete this job?')) {{
                    try {{
                        await fetch(`/jobs/${{jobId}}`, {{ method: 'DELETE' }});
                        document.getElementById(`job-${{jobId}}`).remove();
                        
                        const container = document.getElementById('jobs-container');
                        if (container.children.length === 0) {{
                            container.innerHTML = '<p>No active scraping jobs. Start a scraper above to see progress here.</p>';
                        }}
                        
                        showNotification('Job deleted', 'success');
                    }} catch (error) {{
                        showNotification('Failed to delete job', 'error');
                    }}
                }}
            }}
            
            function showNotification(message, type) {{
                const notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: ${{type === 'success' ? '#28a745' : '#dc3545'}};
                    color: white;
                    padding: 15px 25px;
                    border-radius: 10px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                    z-index: 1000;
                    font-weight: 600;
                    max-width: 300px;
                `;
                notification.textContent = message;
                document.body.appendChild(notification);
                
                setTimeout(() => {{
                    notification.remove();
                }}, 5000);
            }}
            
            // Auto-refresh jobs on page load
            window.onload = async function() {{
                try {{
                    const response = await fetch('/jobs');
                    const jobs = await response.json();
                    
                    if (jobs.length > 0) {{
                        for (const job of jobs) {{
                            updateJobDisplay(job);
                            if (job.status === 'running' || job.status === 'pending') {{
                                activeJobs.add(job.job_id);
                                pollJobStatus(job.job_id);
                            }}
                        }}
                    }}
                }} catch (error) {{
                    console.log('No existing jobs to load');
                }}
            }};
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/scrape")
async def start_scraping(request: ScrapingRequest, background_tasks: BackgroundTasks):
    """Start a scraping job"""
    job_id = str(uuid.uuid4())[:8]
    
    # Merge with default options
    if request.scraper_type == 'classic_valuer':
        options = {**CLASSIC_VALUER_DEFAULT_OPTIONS, **request.options} if SCRAPERS_AVAILABLE else request.options
    elif request.scraper_type == 'classic_com':
        options = {**CLASSIC_COM_DEFAULT_OPTIONS, **request.options} if SCRAPERS_AVAILABLE else request.options
    else:
        raise HTTPException(status_code=400, detail="Invalid scraper type. Use 'classic_valuer' or 'classic_com'")
    
    # Initialize job status
    scraping_jobs[job_id] = {
        'job_id': job_id,
        'status': 'pending',
        'message': f'{request.scraper_type} scraping job queued for processing',
        'progress': 0,
        'total_records': 0,
        'results': [],
        'csv_file': None,
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
        'scraper_type': request.scraper_type,
        'options': options
    }
    
    # Add background task based on scraper type
    if request.scraper_type == 'classic_valuer':
        background_tasks.add_task(run_classic_valuer_background, job_id, options)
    elif request.scraper_type == 'classic_com':
        # For sync functions, we need to wrap in a thread
        def run_in_thread():
            run_classic_com_background(job_id, options)
        
        thread = threading.Thread(target=run_in_thread)
        thread.start()
    
    return {
        "job_id": job_id, 
        "message": f"{request.scraper_type} scraping job started",
        "options": options
    }

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific scraping job"""
    if job_id not in scraping_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return scraping_jobs[job_id]

@app.get("/jobs")
async def get_all_jobs():
    """Get all scraping jobs"""
    return list(scraping_jobs.values())

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download a generated CSV file"""
    file_path = Path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv'
    )

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from memory"""
    if job_id in scraping_jobs:
        # Also try to delete associated files
        job = scraping_jobs[job_id]
        if job.get('csv_file'):
            try:
                Path(job['csv_file']).unlink(missing_ok=True)
            except:
                pass
        
        del scraping_jobs[job_id]
        return {"message": "Job deleted"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@app.get("/results/{job_id}")
async def get_job_results(job_id: str):
    """Get full results for a completed job"""
    if job_id not in scraping_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = scraping_jobs[job_id]
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job not completed")
    
    # If there's a CSV file, read and return all data
    if job['csv_file'] and Path(job['csv_file']).exists():
        try:
            df = pd.read_csv(job['csv_file'])
            return {
                "job_id": job_id,
                "total_records": len(df),
                "data": df.to_dict('records')
            }
        except Exception as e:
            return {"error": f"Failed to read CSV: {str(e)}"}
    
    return {
        "job_id": job_id,
        "results": job.get('results', [])
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "scrapers_available": SCRAPERS_AVAILABLE,
        "active_jobs": len([job for job in scraping_jobs.values() if job['status'] in ['pending', 'running']]),
        "total_jobs": len(scraping_jobs)
    }

@app.get("/api/info")
async def api_info():
    """API information and endpoints"""
    return {
        "title": "Car Auction Scraper API",
        "version": "2.0.0",
        "description": "Web scraper for classic car auction data",
        "scrapers": {
            "classic_valuer": {
                "description": "Scrapes TheClassicValuer.com market data",
                "available": SCRAPERS_AVAILABLE
            },
            "classic_com": {
                "description": "Scrapes Classic.com auction listings", 
                "available": SCRAPERS_AVAILABLE
            }
        },
        "endpoints": {
            "POST /scrape": "Start a scraping job",
            "GET /status/{job_id}": "Get job status",
            "GET /jobs": "Get all jobs",
            "GET /results/{job_id}": "Get full results",
            "GET /download/{filename}": "Download CSV file",
            "DELETE /jobs/{job_id}": "Delete a job"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚗 Starting Car Auction Scraper API...")
    print(f"📊 Scrapers Available: {SCRAPERS_AVAILABLE}")
    print("🌐 Dashboard will be available at: http://localhost:8000")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)