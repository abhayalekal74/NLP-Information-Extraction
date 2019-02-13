import re
import nltk
import sys


def verify_rounding_section_present(cur_page, next_page):
    # In the worst case, if cur_page contains only the "Rounding" word and the next_page contains the actual rounding section, both the pages will be POS tagged.
    # Not worrying about it for now
    rounding_section_present, continued_in_next_page = is_rounding_section_in_page("\n".join([cur_page, next_page]))
    if rounding_section_present and not continued_in_next_page: # These two pages have all the content
        return True
    return False


def is_rounding_section_in_page(page_content):

    # Case sensitive, not using regex because we are looking for an exact match
    _r = "Rounding" in page_content
    _del = "Delivery Amount" in page_content
    _ret = "Return Amount" in page_content
    
    # Regex to match currency and amount.
    # From https://en.wikipedia.org/wiki/ISO_4217 all currency notations are of 3 capital letters.
    amount = re.compile(r'[A-Z]{3}\s*\d+([,]\d+)*')
    amount_present = amount.search(page_content)

    if _r and _del and _ret and amount_present:
        return True, False # Rounding section is present in this page
    elif _r:
        # Rounding is present, but not the entire paragraph. Need to check the next page
        # In case this was just a word and not the section itself, verify_rounding_section_present takes care of this
        return True, True 
    else:
        return False, False


def chunk(tags):
    amount_types = ['', '']
    currencies = ['', '']
    roundings = ['nearest', 'nearest']
    amount_values = ['', '']

    currency_regex = re.compile(r'\b[A-Z]{3}\b') 

    def get_currency_indices(words, tags):
        indices = [i for i, x in enumerate(tags) if x == 'CD']
        # Remove indices which do not have currency as their previous word
        for i in range(len(indices)):
            if not currency_regex.search(words[indices[i] - 1]):
                del indices[i]        
        return indices

    def get_roundings(words, tags):
        try:
            # If index throws an error or the if condition fails, rounding info is not given
            _vbn_index = tags.index('VBN') 
            if _vbn_index < len(tags) - 1 and words[_vbn_index] == 'rounded' and words[_vbn_index + 1] in ['up', 'down']:
                return _vbn_index, True
        except ValueError:
            pass
        return -1, False

    def parse_together_match(words, tags):
        # Check if Delivery and Return are present
        try:
            _del_word_index = words.index('Delivery')
            _ret_word_index = words.index('Return')
        except ValueError:
            # False positive
            return False

        # Storing data in the order of occurence
        _del_data_index = 0 if _del_word_index < _ret_word_index else 1
        _ret_data_index = (_del_data_index + 1) % 2

        amount_types[_del_data_index] = 'Delivery Amount'
        amount_types[_ret_data_index] = 'Return Amount'
    
        # If index throws an error or the if condition fails, rounding info is not given
        _vbn_index, has_roundings = get_roundings(words, tags)
        if has_roundings: 
            # Its given whether the values are rounded up or down
            roundings[0] = words[_vbn_index + 1]

            # Check within the next 3 words if there's another rounding 
            for i in range(_vbn_index + 2, min(len(words), _vbn_index + 5)):
                if words[i] in ['up', 'down']:
                    roundings[1] = words[i]
                    break # Rounding found, break
            if roundings[1] == 'nearest': # For two amounts only one rounding is given, so it must be the same for both
                roundings[1] = roundings[0]

        indices = get_currency_indices(words, tags)
        amount_values[0] = words[indices[0]]
        currencies[0] = words[indices[0] - 1]
        if len(indices) > 1:
            # If both prices are mentioned separately
            amount_values[1] = words[indices[1]]
            currencies[1] = words[indices[1] - 1]
        else:
            # If the prices are the same
            amount_values[1] = amount_values[0]
            currencies[1] = currencies[0]
        return True
            
    def parse_separate_match(words, tags):
        if ('Delivery' in words or 'Return' in words) and 'Amount' in words:
            if len(amount_types[0]) == 0: # Setting amount_types once
                amount_types[0] = 'Delivery Amount'
                amount_types[1] = 'Return Amount'
            active_data_index = 0 if 'Delivery' in words and 'Amount' in words else 1 # Tells whether working with Delivery Amount or Return Amount 
            indices = get_currency_indices(words, tags)
            amount_values[active_data_index] = words[indices[0]]
            currencies[active_data_index] = words[indices[0] - 1]
            _vbn_index, has_roundings = get_roundings(words, tags)
            roundings[active_data_index] = words[_vbn_index + 1] if has_roundings else 'nearest'

    grammar = ('''
               TOGETHER: {<DT>?<NNP>{2}<.*>{0,10}<CC><.*>{0,10}<DT>?<NNP>{2}<.*>{0,5}?(<VBN>(<RP>|<RB>)(<.*>{0,2}(<RP>|<RB>)?))?<.*>{0,10}<NNP><CD>(<.*>{0,4}?<NNP><CD>)?}
               SEPARATE: {<DT>?<NNP>{2}<.*>{0,10}?(<VBN>(<RP>|<RB>))?<.*>{0,10}?<NNP><CD>}  
               ''')

    chunk_regex_parser = nltk.RegexpParser(grammar)
    parsed_tree = chunk_regex_parser.parse(tags)
    subtree_matches = parsed_tree.subtrees(filter=lambda x: x.label() in ['TOGETHER', 'SEPARATE'])

    for match in subtree_matches:
        # In case there are false positive matches for TOGETHER or SEPARATE, handle them by checking for Delivery and Return amount in particular
        words, tags = [], []
        for l in match.leaves():
            words.append(l[0])
            tags.append(l[1])

        if match.label() == 'TOGETHER':
            data_found = parse_together_match(words, tags) # Once the data is found, its safe to break from the loop
            if data_found:
                break
        else:
            parse_separate_match(words, tags) # Delivery and Return amounts are separate, so letting the loop run for all subtrees, check if delivery and return data is found and stop the loop. Skipping for now
        
    if len(amount_types[0]) == 0:
        print ("Could not extract the data, this maybe because of an issue with the data extracted by Tika or the rounding section is not present in the document")
    else:        
        for i in range(2):
            print ("{}: Currency: {} Amount: {} Rounding: {}".format(amount_types[i], currencies[i], amount_values[i], roundings[i]))


def pos_tag(pages):
    page_contents = '\n'.join(pages)
    tags = nltk.pos_tag(nltk.word_tokenize(page_contents))    
    chunk(tags)


def read_pdf(pdf_file):
    from tika import parser
    
    try:
        file_content = parser.from_file(pdf_file)['content']
    except FileNotFoundError:
        sys.exit('File not found, please pass a valid path')

    pagewise_content = [page_content for page_content in file_content.split('\n\n\n\n') if len(page_content) > 0]
    
    num_pages = len(pagewise_content)

    def update_pointers(dir_flag, fwd_ptr, back_ptr):
        if not dir_flag and fwd_ptr >= num_pages:
            # No need to change pointer direction as the forward pointer has reached file's end
            # It is guaranteed that forward pointer will reach file's end before backward pointer reaches the first page because we are starting at q3
            back_ptr -= 1
        else: # Forward pointer has not reached file's end. Continue search in both directions
            if dir_flag:
                fwd_ptr += 1
            else:
                back_ptr -= 1
            dir_flag = not dir_flag
        return dir_flag, fwd_ptr, back_ptr

    # from the 4 pdfs given, its noticeable that the rounding section is generally around the 3rd quartile
    q3 = (int)(0.75 * num_pages)
    backward_pointer = q3 - 1
    forward_pointer = q3
    read_direction_forward = True # If read direction forward is True, use forward pointer else use backward pointer
    
    while(forward_pointer < num_pages or backward_pointer >= 0):
        pointer = forward_pointer if read_direction_forward else backward_pointer # Search a page forward and backward around q3
        cur_page_content = pagewise_content[pointer] 
        rounding_section_present, continued_in_next_page = is_rounding_section_in_page(cur_page_content)
        if rounding_section_present: # If rounding section is found, POS tag page
            if continued_in_next_page: # In case rounding section is continued in next page
                # Make sure this indeed is the rounding section and not just the word "rounding"
                next_page_content = pagewise_content[pointer + 1] 
                if verify_rounding_section_present(cur_page_content, next_page_content):
                    pos_tag([cur_page_content, next_page_content])
                    break # Break the loop because the rounding section has been found
                else:
                    read_direction_forward, forward_pointer, backward_pointer = update_pointers(read_direction_forward, forward_pointer, backward_pointer)
            else:
                pos_tag([cur_page_content])
                break # Break the loop because the rounding section has been found
        else: # Continue search
            read_direction_forward, forward_pointer, backward_pointer = update_pointers(read_direction_forward, forward_pointer, backward_pointer)



if __name__ == '__main__':
    if len(sys.argv) >= 2:
        read_pdf(sys.argv[1])
    else:
        print ("Pass a PDF file to extract data from")
