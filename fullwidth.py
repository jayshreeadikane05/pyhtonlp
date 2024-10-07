from flask import Flask, request, send_file, render_template
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from lxml import html
import io

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form['url']
    
    try:
        existing_html_file = 'fullwidthimg.html'  # Update with your existing HTML file path
        with open(existing_html_file, 'r', encoding='utf-8') as file:
            existing_html_content = file.read()
        
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to retrieve the URL. Status code: {response.status_code}")
            return f"Failed to retrieve the URL. Status code: {response.status_code}", 400
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        page_title_div = soup.find('div', {'id': 'pageTitle'})
        if page_title_div:
            page_title = page_title_div.get_text(strip=True)
        else:
            page_title = "No Title Found"
        
        fullbanner_img = soup.find('div', {'class': 'fullbanner'}).find('img')
        if fullbanner_img:
            fullbanner_url = fullbanner_img['src']
        else:
            fullbanner_url = None
        
       
        main_section = soup.find('section', {'id': 'mainBodyCopy'})
        if not main_section:
            return "Main section 'mainBodyCopy' not found in the page.", 404
        main_section_str = str(main_section)
        
        parser = html.HTMLParser(encoding='utf-8')
        tree = html.parse(io.StringIO(existing_html_content), parser)
        root = tree.getroot()
        
        title_tag = root.find('.//title')
        if title_tag is not None:
            title_tag.text = page_title
        else:
            head_tag = root.find('.//head')
            if head_tag is not None:
                head_tag.append(html.Element('title', text=page_title))
        
        target_section = root.xpath('//*[@id="mainBodyCopy3"]')
        if target_section:
            parent = target_section[0].getparent()
            parent.remove(target_section[0])
            parent.append(html.fragment_fromstring(main_section_str))
         
        else:
            return "Target section 'mainBodyCopy3' not found in the existing HTML.", 404
        
        jumbotron_div = root.xpath('//div[@class="jumbotron"]')
        if jumbotron_div and fullbanner_url:
            jumbotron_div[0].attrib['style'] = f"background: url('{fullbanner_url}') no-repeat; background-size: cover; background-color: #0078D7;"
        
        updated_html_content = html.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')
        with open(existing_html_file, 'w', encoding='utf-8') as file:
            file.write(updated_html_content)
        
        df = pd.DataFrame(columns=['Category', 'Content'])
        df.loc[len(df)] = ['Main Section Content', main_section_str]
        df.loc[len(df)] = ['Page Title', page_title]
        if fullbanner_url:
            df.loc[len(df)] = ['Fullbanner Image URL', fullbanner_url]
        
        # Create Excel file
        excel_file = 'scraped_data.xlsx'
        df.to_excel(excel_file, index=False)
        
        return render_template('download.html', filename_excel=excel_file, filename_html=existing_html_file)

    except Exception as e:
        print(f"An error occurred: {e}")
        return f"An error occurred: {e}", 500

@app.route('/download_excel/<filename>')
def download_excel(filename):
    return send_file(filename, as_attachment=True)

@app.route('/download_html/<filename>')
def download_html(filename):
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
