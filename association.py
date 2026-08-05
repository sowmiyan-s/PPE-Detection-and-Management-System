def get_intersection_over_area(boxA, boxB):
    """
    Calculate the intersection of boxA and boxB divided by the area of boxA.
    Useful for checking if boxA (e.g. a helmet) is inside boxB (e.g. a person).
    box format: [x1, y1, x2, y2]
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    
    if boxAArea == 0:
        return 0.0

    return interArea / float(boxAArea)


def associate_ppe_to_persons(persons, ppe_items, iou_threshold=0.5):
    """
    Associates PPE items to tracked persons based on bounding box overlap.
    
    persons: list of dicts [{'id': int, 'box': [x1, y1, x2, y2], 'class_name': str}]
    ppe_items: list of dicts [{'box': [x1, y1, x2, y2], 'class_name': str, 'confidence': float}]
    
    Returns:
    A mapping from person ID to a list of associated PPE items.
    """
    associations = {person['id']: [] for person in persons}
    
    for ppe in ppe_items:
        best_match_id = None
        best_ioa = 0
        
        # Find which person this PPE item overlaps with the most
        for person in persons:
            ioa = get_intersection_over_area(ppe['box'], person['box'])
            if ioa > best_ioa and ioa > iou_threshold:
                best_ioa = ioa
                best_match_id = person['id']
                
        if best_match_id is not None:
            associations[best_match_id].append({
                'class_name': ppe['class_name'],
                'confidence': ppe['confidence']
            })
            
    return associations
