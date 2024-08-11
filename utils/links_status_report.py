import asyncio
import aiohttp
import re
import webbrowser
import os
from datetime import datetime
from typing import List, Tuple, Dict
from collections import defaultdict

# Constants
MARKDOWN_LINK_RE = r"\[([^\]]+)\]\((http[s]?://[^\s]+)\)"
SEMAPHORE_LIMIT = 30
TIMEOUT = 5

# Custom exception for link checking errors
class LinkCheckError(Exception):
    pass

async def is_link_active(url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore) -> Tuple[str, str]:
    async with semaphore:
        try:
            async with session.head(url, allow_redirects=True, timeout=TIMEOUT) as response:
                return ("Good", "success") if response.status == 200 else (f"{response.status}", "error")
        except asyncio.TimeoutError:
            return ("Bad", "warning")
        except aiohttp.ClientError:
            return ("Bad", "error")

async def check_links_in_markdown(file_path: str) -> List[Tuple[str, str, str, str]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except IOError as e:
        raise LinkCheckError(f"Error reading file {file_path}: {str(e)}")

    links = re.findall(MARKDOWN_LINK_RE, content)
    
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    async with aiohttp.ClientSession() as session:
        tasks = [is_link_active(url, session, semaphore) for _, url in links]
        statuses = await asyncio.gather(*tasks)

    return [
        (text.replace('**', ''), status, url, color)
        for (text, url), (status, color) in zip(links, statuses)
    ]

def generate_html_content(results: Dict[str, List[Tuple[str, str, str, str]]]) -> str:
    css = """
    <style>
        body {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            margin: 0;
            padding: 20px;
            background-color: #282a36;
            color: #f8f8f2;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #ff79c6;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 0 0 10px rgba(255,121,198,0.5);
        }
        h2 {
            color: #8be9fd;
            margin-top: 40px;
            font-size: 1.8em;
            border-bottom: 2px solid #6272a4;
            padding-bottom: 10px;
        }
        table {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            max-width: 1160px; /* Adjusted to account for container padding */
            margin-bottom: 30px;
            background-color: #44475a;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            table-layout: fixed;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #6272a4;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        th {
            background-color: #3c3f58;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #50fa7b;
        }
        th:nth-child(1), td:nth-child(1) { width: 30%; } /* Link Text */
        th:nth-child(2), td:nth-child(2) { width: 10%; } /* Status */
        th:nth-child(3), td:nth-child(3) { width: 60%; } /* URL */
        tr:last-child td {
            border-bottom: none;
        }
        tr:hover {
            background-color: #4f5268;
        }
        a {
            color: #8be9fd;
            text-decoration: none;
            transition: color 0.3s ease, text-shadow 0.3s ease;
        }
        a:hover {
            color: #ff79c6;
            text-shadow: 0 0 5px rgba(255,121,198,0.5);
        }
        .status {
            font-weight: bold;
            text-align: center;
        }
        .success { color: #50fa7b; text-shadow: 0 0 5px rgba(80,250,123,0.5); }
        .error { color: #ff5555; text-shadow: 0 0 5px rgba(255,85,85,0.5); }
        .warning { color: #ffb86c; text-shadow: 0 0 5px rgba(255,184,108,0.5); }
        .summary {
            background-color: #3c3f58;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        .summary h3 {
            color: #ff79c6;
            margin-top: 0;
        }
        .summary ul {
            list-style-type: none;
            padding: 0;
        }
        .summary li {
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .summary .stat-label {
            color: #8be9fd;
        }
        .summary .stat-value {
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
            background-color: #44475a;
        }
        .timestamp {
            text-align: center;
            margin-top: 20px;
            font-style: italic;
            color: #6272a4;
        }
        .file-path {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            background-color: #3c3f58;
            padding: 5px 10px;
            border-radius: 4px;
            color: #50fa7b;
            font-size: 0.9em;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            display: inline-block;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
    </style>
    """

    total_links = sum(len(links) for links in results.values())
    successful_links = sum(sum(1 for _, status, _, _ in links if status == "Good") for links in results.values())
    failed_links = total_links - successful_links

    html_content = f"""
    <html>
    <head>
        <title>Link Status Report</title>
        {css}
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="container">
            <h1>Link Status Report</h1>
            <div class="summary">
                <h3>Summary</h3>
                <ul>
                    <li><span class="stat-label">Total files scanned:</span> <span class="stat-value">{len(results)}</span></li>
                    <li><span class="stat-label">Total links checked:</span> <span class="stat-value">{total_links}</span></li>
                    <li><span class="stat-label">Successful links:</span> <span class="stat-value success">{successful_links}</span></li>
                    <li><span class="stat-label">Failed links:</span> <span class="stat-value error">{failed_links}</span></li>
                </ul>
            </div>
    """

    for file, links in results.items():
        html_content += f'<h2><span class="file-path">{os.path.relpath(file)}</span></h2>'
        html_content += "<table><tr><th>Link Text</th><th class='status'>Status</th><th>URL</th></tr>"

        for text, status, url, color in links:
            html_content += f"<tr><td>{text}</td><td class='status {color}'>{status}</td><td><a href='{url}' target='_blank'>{url}</a></td></tr>"

        html_content += "</table>"

    html_content += f"""
            <div class="timestamp">Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
    </body>
    </html>
    """

    return html_content

async def generate_report(folder_path: str, report_path: str) -> str:
    markdown_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(folder_path)
        for file in files if file.endswith('.md')
    ]
    
    results = {}
    for file in markdown_files:
        try:
            results[file] = await check_links_in_markdown(file)
        except LinkCheckError as e:
            print(f"Error processing file {file}: {str(e)}")

    html_content = generate_html_content(results)

    with open(report_path, 'w', encoding='utf-8') as report_file:
        report_file.write(html_content)

    return 'file://' + os.path.realpath(report_path)

async def main():
    try:
        markdown_folder_path = '../docs'
        report_path = '../docs/links_status_report.html'
        report_url = await generate_report(markdown_folder_path, report_path)
        print(f"Link status report generated for markdown files in {markdown_folder_path}")
        print(f"Report available at: {report_url}")
        webbrowser.open(report_url)
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())