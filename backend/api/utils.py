import cv2
import numpy as np
from PIL import Image

from django.conf import settings

import logging, logging.config


logging.config.dictConfig(settings.LOGGING)

def get_image_contours(image, cut_off = 95, dilate=False, sharpen=False, faded = False):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_use = gray.copy()

    if faded:   
        blur = cv2.GaussianBlur(gray, (3,3), 0)        
        (threshold, binaryImage) = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        threshold = 1.015 * threshold
        
        _, binaryImage = cv2.threshold(blur, threshold, 255, cv2.THRESH_BINARY_INV)
        
        sharpen_kernel = np.array([
            [+0, -1, +0],
            [-1, +5, -1],
            [+0, -1, +0]
        ])
    
        lower_gray = np.array([0,0,100])
        upper_gray = np.array([255, 5, 255])
        
        sharpened = cv2.filter2D(image, -1, sharpen_kernel)
        hsv = cv2.cvtColor(sharpened.copy(), cv2.COLOR_BGR2HSV)
        mask_grey = cv2.inRange(hsv, lower_gray, upper_gray)
        
        # Build mask of non-black pixels.
        nzmask = cv2.inRange(hsv, (0, 0, 5), (255, 255, 255))
        
        # Erode the mask - all pixels around a black pixels should not be masked.
        nzmask = cv2.erode(nzmask, np.ones((3,3)))
        mask_grey = mask_grey & nzmask
        
        processed_img = image.copy()
        processed_img[np.where(mask_grey)] = 255
        
        gray = cv2.cvtColor(processed_img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3,3), 0)
        threshold = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        morph_threshold = threshold[1]
        
        # Fix reference marks boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(morph_threshold, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        contours = cv2.findContours(closed.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours[0] if len(contours) == 2 else contours[1]
        
        return binaryImage, contours
    
    else:
    
        if dilate:
            equalized = cv2.equalizeHist(gray)
            thresh = cv2.adaptiveThreshold(equalized, 255,
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY_INV, 9, 2)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)) #default=3
            dilated = cv2.dilate(thresh, kernel, iterations=1)
            image_use = dilated.copy() 
            
        if sharpen:
            sharpen_kernel = np.array([
                [-1, -1, -1],
                [-1,  9, -1],
                [-1, -1, -1]
            ])
            
            sharpened = cv2.filter2D(image, -1, sharpen_kernel)
            image_use = cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY)        
        
        _, bw = cv2.threshold(image_use, cut_off, 255, cv2.THRESH_BINARY) # convert to black&white
        _, thresh = cv2.threshold(bw, 50, 255, cv2.THRESH_BINARY_INV)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return bw, contours



def get_fiducials(contours, image, gray_cutoff, rect_size=(2200,4400), aspect=(0.725,1.35), invert= False):

    # Filter for square-like contours    
    area_low, area_high = rect_size
    ratio_low, ratio_high = aspect
    
    fiducials = []
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02*cv2.arcLength(contour, True), True)
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = np.round(w / float(h),2)

        if len(approx) > 3 and (ratio_low <= aspect_ratio <= ratio_high) and (area_low < area < area_high): # Square with reasonable area

            roi = image.copy()[y:y+h, x:x+w]
            grey_pixels_roi = float(cv2.countNonZero(roi))
            all_pixels_roi = float(roi.shape[0]*roi.shape[1])

            if invert:
                percent_black_roi = np.round(((grey_pixels_roi/all_pixels_roi)*100), 2)
            else:
                percent_black_roi = 100 - np.round(((grey_pixels_roi/all_pixels_roi)*100), 2)

            if percent_black_roi > gray_cutoff:
                fiducials.extend([(x,y), (x+w, y), (x, y+h), (x+w, y+h)])

    return fiducials

def get_extreme_points(candidate_fiducials):

    pts = np.array(candidate_fiducials)

    # Calculate sums and differences
    sums = pts.sum(axis=1)        # x + y
    diffs = np.diff(pts, axis=1)  # x - y

    # Find corners
    rect = np.zeros((4, 2), dtype="float32")
    rect[0] = pts[np.argmin(sums)]  # top-left
    rect[2] = pts[np.argmax(sums)]  # bottom-right
    rect[1] = pts[np.argmin(diffs)] # top-right
    rect[3] = pts[np.argmax(diffs)] # bottom-left

    return rect

def get_pil_image(corners, image):

    (widthA, widthB) = [np.linalg.norm(corners[2] - corners[3]), np.linalg.norm(corners[1] - corners[0])]
    (heightA, heightB) = [np.linalg.norm(corners[1] - corners[2]), np.linalg.norm(corners[0] - corners[3])]

    maxWidth = int(max(widthA, widthB))
    maxHeight = int(max(heightA, heightB))

    # Destination rectangle (straightened)
    extracted_roi = np.array([
        [0, 0],
        [maxWidth + 1, 0],
        [maxWidth + 1, maxHeight + 1],
        [0, maxHeight + 1]
    ], dtype="float32")

    # Compute perspective transform matrix and warp the image
    M = cv2.getPerspectiveTransform(corners, extracted_roi)
    warped = cv2.warpPerspective(image, M, (maxWidth + 1, maxHeight + 1))

    pil_image = Image.fromarray(warped)

    return pil_image


def find_best_template(image, 
                       template_path_list,                       
                       method=cv2.TM_CCOEFF_NORMED):    
    

    # Load the target image (convert to grayscale for template matching)
    target_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) 
        
    best_match = None
    best_value = -np.inf  # Because we're using a method where higher is better
    best_location = None
    best_template_name = None

    for template_path in template_path_list:
        template_img = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        #template_img = cv2.equalizeHist(template_img)

        if template_img is None:
            continue  # Skip if not an image

        # Resize template if it's larger than the target
        if (template_img.shape[0] > target_img.shape[0] or 
            template_img.shape[1] > target_img.shape[1]):
            
            scale_y = target_img.shape[0] / template_img.shape[0]
            scale_x = target_img.shape[1] / template_img.shape[1]
            scale = min(scale_y, scale_x)
            
            new_size = (int(template_img.shape[1] * scale), int(template_img.shape[0] * scale))
            template_img = cv2.resize(template_img, new_size, interpolation=cv2.INTER_AREA)

        # Ensure final size is valid
        if (template_img.shape[0] > target_img.shape[0] or 
            template_img.shape[1] > target_img.shape[1]):
            print(f"Skipping {template_path}: still too large after resize")
            continue


        # Match template
        result = cv2.matchTemplate(target_img, template_img, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_CCOEFF_NORMED, higher score means better match
        match_val = max_val if method in [cv2.TM_CCOEFF, cv2.TM_CCOEFF_NORMED,
                                          cv2.TM_CCORR, cv2.TM_CCORR_NORMED] else -min_val

        if match_val > best_value:
            best_value = match_val
            best_match = template_img
            best_location = max_loc if method in [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED] else min_loc
            best_template_name = template_path

    return best_template_name, best_value, best_location


def get_template_akaze_score(image_gray, template_path):
    # Convert image to grayscale

    #target_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    target_img = image_gray.copy()

    # Create AKAZE detector
    akaze = cv2.AKAZE_create(
        threshold=5e-6,
        descriptor_size=0
    )

    # Detect keypoints and descriptors in the target image
    keypoints_img, descriptors_img = akaze.detectAndCompute(target_img, None)

    template_img = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

    keypoints_template, descriptors_template = akaze.detectAndCompute(template_img, None)

    # Match using Brute-Force matcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)

    #Lowe’s ratio test to filter good matches.
    raw_matches = bf.knnMatch(descriptors_img, descriptors_template, k=2) 

    good_matches = []
    for pair in raw_matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.7 * n.distance: # Lowe’s ratio test
            good_matches.append(m)
            

    matches = bf.match(descriptors_img, descriptors_template)
    matches = sorted(matches, key=lambda x: x.distance)

    # Use top N matches for score (lower distance = better)
    match_ratio = len(good_matches) / len(keypoints_img)
    
    return match_ratio



def find_best_template_akaze(image_path, template_path_list):
    # Convert image to grayscale

    image = cv2.imread(image_path)
    target_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    #target_img = cv2.equalizeHist(target_img)

    # Create AKAZE detector
    akaze = cv2.AKAZE_create(
        threshold=1e-5,
        descriptor_size=0
    )

    # Detect keypoints and descriptors in the target image
    keypoints_img, descriptors_img = akaze.detectAndCompute(target_img, None)

    best_template = None
    best_match_score = -np.inf
    best_template_name = None
    best_matches = None
    beat_match_ratio = 0.0

    for template_path in template_path_list:
        template_img = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template_img is None:
            continue

        #template_img = cv2.equalizeHist(template_img)
        keypoints_template, descriptors_template = akaze.detectAndCompute(template_img, None)

        if descriptors_template is None or descriptors_img is None:
            continue

        # Match using Brute-Force matcher
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)

        #Lowe’s ratio test to filter good matches.
        raw_matches = bf.knnMatch(descriptors_img, descriptors_template, k=2) 

        good_matches = []
        for m, n in raw_matches:
            if m.distance < 0.7 * n.distance:  # Lowe’s ratio test
                good_matches.append(m)

        matches = bf.match(descriptors_img, descriptors_template)
        matches = sorted(matches, key=lambda x: x.distance)

        # Use top N matches for score (lower distance = better)

        match_ratio = len(good_matches) / len(keypoints_img)
        #if match_ratio > 0.05:
        logging.info(f"page: {image_path.split('/')[-1]}, template: {template_path.split('/')[-1]}, match_ratio: {match_ratio}")

        '''
        top_matches = matches[:min(len(matches), 20)]
        score = -np.mean([m.distance for m in top_matches])  # higher score = better

        logging.info(f"page: {image_path.split('/')[-1]}, template: {template_path.split('/')[-1]}, score: {score}\n")
        

        if len(top_matches) >= min_good_matches and score > best_match_score:
            best_match_score = score
            best_template = template_img
            best_template_name = template_path
            best_matches = top_matches
        '''

        if match_ratio > beat_match_ratio:
            best_template = template_img
            best_template_name = template_path
            beat_match_ratio = match_ratio

    return best_template_name


def align_image_to_template(target_image, template_path, good_match_percent=0.15, 
                            method_use = "AKAZE", max_features=500):
    # Load images in grayscale
    #target_image = cv2.cvtColor(target_image, cv2.IMREAD_GRAYSCALE)
    template_use = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)

    if target_image is None or template_use is None:
        raise ValueError("Could not load images for registration.")

    # Detect ORB features and compute descriptors
    if method_use == "ORB":
        orb = cv2.ORB_create(max_features)
        keypoints_img, descriptors_img = orb.detectAndCompute(target_image, None)
        keypoints_template, descriptors_template = orb.detectAndCompute(template_use, None)

    else: #Use AKAZE
        akaze = cv2.AKAZE_create(
            threshold=1e-6,
            descriptor_size=0
        )
        keypoints_img, descriptors_img = akaze.detectAndCompute(target_image, None)
        keypoints_template, descriptors_template = akaze.detectAndCompute(template_use, None)

        if descriptors_img is None or descriptors_template is None:
               raise RuntimeError("Could not compute AKAZE descriptors.")

    # Match features using Brute Force matcher
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(descriptors_img, descriptors_template)
    matches = sorted(matches, key=lambda x: x.distance)

    # Use only the top matches
    num_good_matches = int(len(matches) * good_match_percent)
    matches = matches[:num_good_matches]

    points_image = np.float32([keypoints_img[m.queryIdx].pt for m in matches])
    points_template = np.float32([keypoints_template[m.trainIdx].pt for m in matches])
    
    # Find homography matrix
    h, mask = cv2.findHomography(points_image, points_template, cv2.RANSAC)

    if (h is None) | (len(matches) < 4):
        raise RuntimeError("Homography could not be computed. Not enough matches.")

    # Warp the target image to align with the template
    height, width = template_use.shape
    aligned_image = cv2.warpPerspective(
        target_image, 
        h, 
        (width, height))
    
    pil_image = Image.fromarray(aligned_image)

    return pil_image, width, height