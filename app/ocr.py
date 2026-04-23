"""
ocr.py – Extract expense details from receipt files (image/PDF/DOCX).
"""

import re
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    'food': ['restaurant', 'cafe', 'pizza', 'burger', 'sushi', 'food', 'dining', 'coffee', 'tea', 'bakery', 'grill', 'bar', 'eat', 'diner', 'kitchen', 'subway', 'mcdonalds', 'kfc', 'starbucks', 'dominos', 'swiggy', 'zomato'],
    'travel': ['uber', 'ola', 'lyft', 'taxi', 'bus', 'train', 'flight', 'airline', 'hotel', 'booking', 'airbnb', 'petrol', 'fuel', 'gas station', 'toll', 'metro', 'railway', 'travel', 'transport'],
    'shopping': ['amazon', 'flipkart', 'walmart', 'mall', 'store', 'shop', 'market', 'supermarket', 'grocery', 'clothing', 'fashion', 'nike', 'adidas'],
    'bills': ['electricity', 'water', 'internet', 'wifi', 'phone', 'mobile', 'bill', 'utility', 'rent', 'insurance', 'emi', 'recharge', 'postpaid', 'prepaid'],
    'health': ['pharmacy', 'hospital', 'clinic', 'doctor', 'medicine', 'medical', 'dental', 'lab', 'diagnostic', 'chemist', 'health', 'gym', 'fitness'],
    'entertainment': ['cinema', 'movie', 'theatre', 'netflix', 'spotify', 'game', 'park', 'concert', 'event', 'ticket', 'play', 'show', 'bowling', 'arcade'],
}

def suggest_category(text: str) -> str:
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return 'others'

def extract_total(text: str) -> str:
    patterns = [
        r'(?:grand\s*total|total\s*amount|amount\s*due|total\s*due|net\s*total|sub total)[:\s]*([₹\$\s]*\d[\d,\s]*\.\d{2})',
        r'(?:total|amount|total\s*due)[:\s]*([₹\$\s]*\d[\d,\s]*\.\d{2})',
        r'TOTAL\s*:?\s*([₹\$\s]*\d[\d,\s]*\.\d{2})',
        r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*$',
        r'([₹\$\s]*\d{1,3}(?:,\d{3})*(?:,\d{3})*\.\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            amount = re.sub(r'[₹\$\s,]', '', match.group(1))
            logger.info(f"Total extracted: '{match.group(1)}' → '{amount}'")
            return amount
    return ''

def extract_date(text: str) -> str:
    logger.info(f"Extracting date from text (first 200 chars): {text[:200]}...")
    
    # Label-aware patterns first (higher priority)
    label_patterns = [
        r"(?:booking date|date|invoice date|date\s*:?)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?:date|booking)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]
    
    # Generic date patterns
    generic_patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
        r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})',
    ]
    
    all_patterns = label_patterns + generic_patterns
    date_formats = [
        '%d-%m-%Y', '%d/%m/%Y', '%d-%m-%y', '%d/%m/%y',
        '%m-%d-%Y', '%m/%d/%Y', '%m-%d-%y', '%m/%d/%y',
        '%Y-%m-%d', '%Y/%m/%d',
        '%d %B %Y', '%d %b %Y',
    ]
    
    candidates = []
    for pattern in all_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            raw = match.group(1)
            logger.debug(f"Trying date candidate: '{raw}'")
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(raw, fmt)
                    # Handle 2-digit years: 00-49 → 2000-2049, 50-99 → 1950-1999
                    if dt.year < 100:
                        if dt.year < 50:
                            dt = dt.replace(year=2000 + dt.year)
                        else:
                            dt = dt.replace(year=1900 + dt.year)
                    candidates.append((dt.strftime('%Y-%m-%d'), raw, pattern))
                    logger.debug(f"Valid date found: {dt.strftime('%Y-%m-%d')} from '{raw}' with {fmt}")
                    break  # First matching format per candidate
                except ValueError:
                    continue
    
    if candidates:
        # Return the first label-aware or earliest/latest reasonable date
        logger.info(f"Found {len(candidates)} date candidates, using first: {candidates[0][0]}")
        return candidates[0][0]
    
    logger.warning("No valid dates found, using today")
    return datetime.today().strftime('%Y-%m-%d')

def extract_merchant(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    address_words = ['street', 'st.', 'road', 'rd.', 'avenue', 'ave', 'lane', 'blvd', 'floor', 'suite', 'tel', 'phone', 'fax', 'www.', 'http']
    for line in lines[:5]:
        if len(line) < 3:
            continue
        line_lower = line.lower()
        if any(w in line_lower for w in address_words):
            continue
        if re.match(r'^\d', line):
            continue
        return line[:80]
    return ''

def process_receipt(file_path: str) -> dict:
    raw_text = ''
    temp_images = []
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']:
            temp_images.append(file_path)
        elif ext == '.pdf':
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(file_path, first_page=1, last_page=3, dpi=200)
                if images:
                    for i, img in enumerate(images[:2]):
                        temp_img_path = file_path.rsplit('.', 1)[0] + f'_p{i+1}.jpg'
                        img.save(temp_img_path, 'JPEG', quality=95)
                        temp_images.append(temp_img_path)
                    logger.info('PDF → %d pages @200dpi', len(temp_images))
                else:
                    raise ValueError('No pages extracted')
            except Exception as e:
                logger.warning('PDF failed: %s', e)
                return {'error': f'PDF failed (needs poppler in PATH): {str(e)}', 'raw_text': ''}
        elif ext == '.docx':
            from docx import Document
            doc = Document(file_path)
            raw_text = '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
            logger.info('DOCX extracted')
        
        # OCR all temp images
        if temp_images and not raw_text:
            try:
                import easyocr
                reader = easyocr.Reader(['en'], gpu=False)
                for temp_image in temp_images:
                    results = reader.readtext(temp_image, detail=0, paragraph=True)
                    page_text = '\n'.join(results)
                    raw_text += page_text + '\n\n'
                    logger.info('OCR page: %d chars', len(page_text))
                raw_text = raw_text.strip()
                if len(raw_text) < 20:
                    logger.warning('Poor OCR total text')
            except Exception as e:
                logger.error('EasyOCR failed: %s', e)
        
        # Cleanup
        for temp_img in temp_images:
            if temp_img != file_path and os.path.exists(temp_img):
                os.remove(temp_img)
                
    except Exception as exc:
        logger.error('Process receipt error: %s', exc)
    
    result = {
        'raw_text': raw_text,
        'total': extract_total(raw_text),
        'date': extract_date(raw_text),
        'merchant': extract_merchant(raw_text),
        'category': suggest_category(raw_text),
    }
    if not raw_text:
        result['error'] = 'No text. PDFs need poppler: https://github.com/oschwartz10612/poppler-windows/releases - extract bin/ to C:\\poppler, add to PATH.'
    return result

