import asyncio
import aiohttp
import re
import webbrowser
import os

# Regular expression to find Markdown links
markdown_link_re = r"\[([^\]]+)\]\((http[s]?://[^\s]+)\)"

async def is_link_active(url, session, semaphore):
    async with semaphore:  # Limit the number of concurrent requests
        try:
            async with session.head(url, allow_redirects=True, timeout=5) as response:
                return ("✓", "green") if response.status == 200 else (f"{response.status}", "red")
        except asyncio.TimeoutError:
            return ("✕", "orange")
        except aiohttp.ClientError as e:
            return ("✕", "red")

async def check_links_in_markdown(file_path):
    results = []

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    links = re.findall(markdown_link_re, content)
    
    semaphore = asyncio.Semaphore(30)  # Adjust the concurrency level as needed

    async with aiohttp.ClientSession() as session:
        tasks = [is_link_active(url, session, semaphore) for _, url in links]
        statuses = await asyncio.gather(*tasks)

    for (text, url), (status, color) in zip(links, statuses):
        # remove '**' from text
        text = text.replace('**', '')
        results.append((text, status, url, color))

    return results

async def generate_report(folder_path, report_path):
    markdown_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.md'):
                markdown_files.append(os.path.join(root, file))
    
    html_content = """
    <html>
    <head>
        <title>Link Status Report</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #1c1c1c;
                color: #f2f2f2;
            }
            h1 {
                color: #f2f2f2;
                text-align: center;
                margin-bottom: 30px;
            }
            h2 {
                color: #f2f2f2;
                margin-top: 40px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 30px;
            }
            th, td {
                border: 1px solid #444;
                padding: 12px;
                text-align: left;
            }
            th {
                background-color: #333;
                font-weight: bold;
            }
            tr:nth-child(even) {
                background-color: #282828;
            }
            a {
                color: #6fb3d2;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .status {
                font-weight: bold;
                text-align: center;
                width: 60px;
            }
            .green {
                color: #8bc34a;
            }
            .red {
                color: #f44336;
            }
            .orange {
                color: #ff9800;
            }
        </style>
    </head>
    <body>
        <h1>Link Status Report</h1>
    """

    for file in markdown_files:
        results = await check_links_in_markdown(file)

        html_content += f"<h2>{file}</h2>"
        html_content += "<table><tr><th>Link Text</th><th class='status'>Status</th><th>URL</th></tr>"

        for text, status, url, color in results:
            html_content += f"<tr><td>{text}</td><td class='status {color}'>{status}</td><td><a href='{url}' target='_blank'>{url}</a></td></tr>"

        html_content += "</table>"

    html_content += "</body></html>"

    with open(report_path, 'w', encoding='utf-8') as report_file:
        report_file.write(html_content)

    report_path = 'file://' + os.path.realpath(report_path)
    webbrowser.open(report_path)
    return report_path

if __name__ == "__main__":
    markdown_folder_path = '../docs'
    report_path = '../links_status_report.html'
    report_path = asyncio.run(generate_report(markdown_folder_path, report_path))
    print(f"Link status report generated for markdown files in {markdown_folder_path} at {report_path}")